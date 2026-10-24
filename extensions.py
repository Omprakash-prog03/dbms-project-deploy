"""Application extensions configured by the Flask factory."""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# The selected free host runs one worker. Limits are per process and reset on
# restart; a multi-worker deployment should configure a shared storage backend.
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri="memory://",
    default_limits=[],
    headers_enabled=True,
)
