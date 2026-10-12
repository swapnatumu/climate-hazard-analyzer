from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import get_settings


def client_ip(request: Request) -> str:
    """Rate-limit key: the client address as reported by infrastructure we trust.

    X-Forwarded-For is never read: a client can seed it with any value. Behind a proxy,
    set CLIENT_IP_HEADER to a header the proxy overwrites (Render sits behind Cloudflare,
    which sets CF-Connecting-IP). Without it the key is the socket peer address.
    """
    header = get_settings().client_ip_header
    if header:
        value = request.headers.get(header, "").strip()
        if value:
            return value
    return get_remote_address(request)


# Per-client-IP limits. In-memory storage: fine for one instance.
limiter = Limiter(key_func=client_ip)
