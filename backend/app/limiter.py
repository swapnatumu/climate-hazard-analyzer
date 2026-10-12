from slowapi import Limiter
from slowapi.util import get_remote_address

# Per-client-IP limits. Behind a proxy (Render), run uvicorn with --proxy-headers so the
# client IP comes from X-Forwarded-For. In-memory storage: fine for one instance.
limiter = Limiter(key_func=get_remote_address)
