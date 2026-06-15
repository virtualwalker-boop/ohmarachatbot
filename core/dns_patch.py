import socket
import sys

# Force IPv4 DNS resolution to prevent connection hangs over IPv6 
# in dual-stack environments where IPv6 routing is broken or blocked.
_original_getaddrinfo = socket.getaddrinfo

def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    # Unconditionally force IPv4
    family = socket.AF_INET
    return _original_getaddrinfo(host, port, family, type, proto, flags)

socket.getaddrinfo = _ipv4_getaddrinfo

# Print confirmation to stderr (safe from UnicodeEncodeError)
sys.stderr.write("--> DNS Patch: Forced IPv4 DNS resolution successfully applied!\n")
sys.stderr.flush()
