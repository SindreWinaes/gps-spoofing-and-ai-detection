#
# socket.py
# Thin re-export of Python's stdlib socket.socket. The EA model lists
# this class to document that Receiver uses UDP sockets; this file is
# how that documented dependency points at the real stdlib class.
#
# Note: this file is named socket.py to match the EA-modelled class
# name. Inside this file `import socket` resolves to the stdlib socket
# (Python 3's absolute-import default), because the full dotted name
# of THIS module is Pc_backend.Runtime.socket, not socket. From outside
# the package, callers do `from Pc_backend.Runtime.socket import socket`
# to get this re-export, or just `import socket` for the stdlib.
#

import socket as _stdlib_socket


# Re-exports so `from Pc_backend.Runtime.socket import socket, AF_INET, SOCK_DGRAM`
# works as the EA diagram suggests.
socket = _stdlib_socket.socket
AF_INET = _stdlib_socket.AF_INET
SOCK_DGRAM = _stdlib_socket.SOCK_DGRAM
