import hashlib
import hmac

from src.config import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


def validate_github_signature(payload: bytes, signature_header: str) -> bool:
    """Verify X-Hub-Signature-256 HMAC-SHA256 header from GitHub."""
    if not signature_header or not signature_header.startswith("sha256="):
        logger.warning("Missing or malformed GitHub signature header")
        return False

    expected = hmac.new(
        settings.github_webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()

    received = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, received)
