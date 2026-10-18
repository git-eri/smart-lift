"""Controller authentication shared by WebSocket registration and OTA downloads."""

import hmac
import os


def controller_token_valid(presented_token: str | None) -> bool:
    """Allow an unset token for trusted LAN deployments; otherwise compare bytes.

    Request headers may contain non-ASCII text. Encoding both inputs avoids the
    TypeError raised by compare_digest(str, str) for such unauthenticated input.
    Never include either token in a response or diagnostic message.
    """
    configured_token = os.environ.get("SMARTLIFT_CONTROLLER_TOKEN", "")
    if not configured_token:
        return True
    try:
        return hmac.compare_digest(
            (presented_token or "").encode("utf-8"), configured_token.encode("utf-8")
        )
    except UnicodeError:
        return False
