import datetime
import glob
import os
import platform
import shutil

from invoke import task
from invoke.exceptions import Exit

from .build_tags import get_default_build_tags
from .system_probe import CURRENT_ARCH
from .utils import (
    REPO_PATH,
    bin_name,
    get_build_flags,
    get_git_branch_name,
    get_git_commit,
    get_go_version,
    get_version,
)

BIN_DIR = os.path.join(".", "bin")
BIN_PATH = os.path.join(BIN_DIR, "cws-instrumentation", bin_name("cws-instrumentation"))
AGENT_TAG = "datadog/cws-instrumentation:master"
CONTAINER_PLATFORM_MAPPING = {"aarch64": "arm64", "amd64": "amd64", "x86_64": "amd64"}


@task(iterable=["build_tags"])
def build(
    ctx,
    build_tags,
    race=False,
    incremental_build=True,
    major_version='7',
    # arch is never used here; we keep it to have a
    # consistent CLI on the build task for all agents.
    arch=CURRENT_ARCH,  # noqa: U100
    go_mod="mod",
    static=False,
):
    """
    Build cws-instrumentation
    """
    ldflags, gcflags, env = get_build_flags(ctx, major_version=major_version, python_runtimes='3', static=static)

    # TODO use pkg/version for this
    main = "main."
    ld_vars = {
        "Version": get_version(ctx, major_version=major_version),
        "GoVersion": get_go_version(),
        "GitBranch": get_git_branch_name(),
        "GitCommit": get_git_commit(),
        "BuildDate": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
    }

    ldflags += ' '.join([f"-X '{main + key}={value}'" for key, value in ld_vars.items()])
    build_tags += get_default_build_tags(
        build="cws-instrumentation"
    )  # TODO/FIXME: Arch not passed to preserve build tags. Should this be fixed?
    build_tags.append("netgo")
    build_tags.append("osusergo")

    race_opt = "-race" if race else ""
    build_type = "" if incremental_build else "-a"
    go_build_tags = " ".join(build_tags)
    agent_bin = BIN_PATH

    cmd = (
        f'go build -mod={go_mod} {race_opt} {build_type} -tags "{go_build_tags}" '
        f'-o {agent_bin} -gcflags="{gcflags}" -ldflags="{ldflags} -s -w" {REPO_PATH}/cmd/cws-instrumentation'
    )

    ctx.run(cmd, env=env)


@task
def image_build(ctx, arch=None, tag=AGENT_TAG, push=False):
    """
    Build the docker image
    """
    if arch is None:
        arch = CONTAINER_PLATFORM_MAPPING.get(platform.machine().lower())

    if arch is None:
        print("Unable to determine architecture to build, please set `arch` parameter")
        raise Exit(code=1)

    cws_instrumentation_binary = glob.glob(BIN_PATH)
    # get the last debian package built
    if not cws_instrumentation_binary:
        print(f"{BIN_PATH} not found")
        print("See cws-instrumentation.build")
        raise Exit(code=1)

    latest_file = max(cws_instrumentation_binary, key=os.path.getctime)
    ctx.run(f"chmod +x {latest_file}")

    build_context = "Dockerfiles/cws-instrumentation"
    exec_path = f"{build_context}/cws-instrumentation.{arch}"
    dockerfile_path = f"{build_context}/Dockerfile"

    shutil.copy2(latest_file, exec_path)
    ctx.run(f"docker build -t {tag} --platform linux/{arch} {build_context} -f {dockerfile_path}")
    ctx.run(f"rm {exec_path}")

    if push:
        ctx.run(f"docker push {tag}")
