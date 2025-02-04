#!/usr/bin/env python3

import os
import random
import socket
import sys
import time

children = []
port = random.randrange(32768, 65535)
print(port)
count = range(2)
for _ in count:
    child = os.fork()
    if child:
        children.append(child)
    else:
        s = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("localhost", port))
        _, _, _, addr = s.recvmsg(1024)
        s.sendto(b'bar', addr)
        s.close()
        sys.exit()

time.sleep(1)

conns = []
for _x in count:
    c = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM, proto=socket.IPPROTO_UDP)
    c.sendto(b'foobar', ("localhost", port))
    c.recvmsg(1024)
    conns.append(c)

for c in conns:
    c.close()

for child in children:
    _, rc = os.waitpid(child, 0)
    assert rc == 0, "child process exited with non-zero exit code"
