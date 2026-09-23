import logging
import re


class RedactSecretsFilter(logging.Filter):
    """Prevent access tokens, client secrets, and passwords from being logged."""

    _PATTERNS = [
        re.compile(r"(?i)(authorization:\s*bearer\s+)\S+"),
        re.compile(r"(?i)(client_secret=)[^&\s]+"),
        re.compile(r"(?i)(access_token=)[^&\s]+"),
        re.compile(r"(?i)(refresh_token=)[^&\s]+"),
        re.compile(r"(?i)(password=)[^&\s]+"),
        re.compile(r"(?i)(code=)[A-Za-z0-9._~-]{10,}"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        for pattern in self._PATTERNS:
            msg = pattern.sub(r"\1[REDACTED]", msg)
        record.msg = msg
        record.args = ()
        return True
