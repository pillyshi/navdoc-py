class NavdocError(Exception):
    """Base exception for navdoc SDK."""


class AuthError(NavdocError):
    """navdoc API key authentication failed (401/403)."""


class MissingAnthropicKeyError(NavdocError):
    """Anthropic API key is not set when ask() is called."""


class MCPError(NavdocError):
    """MCP protocol-level error (connection failure, etc.)."""

    def __init__(self, message: str, original: Exception | None = None) -> None:
        super().__init__(message)
        self.original = original


class MaxIterationsError(NavdocError):
    """tool_use loop reached max_iterations without an end_turn."""

    def __init__(self, iterations: int) -> None:
        super().__init__(f"Reached max_iterations={iterations} without a final answer.")
        self.iterations = iterations
