class NavdocError(Exception):
    """Base exception for navdoc SDK."""


class AuthError(NavdocError):
    """navdoc API key authentication failed (401/403)."""
