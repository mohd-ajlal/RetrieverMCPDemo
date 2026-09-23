"""Resource audience validators for RFC 8707."""


def exact_resource_match(request_uri: str, audiences: list[str]) -> bool:
    """Require exact audience match against the MCP resource URL."""
    if not audiences:
        return False
    normalized = request_uri.rstrip("/")
    return any(normalized == aud.rstrip("/") for aud in audiences)
