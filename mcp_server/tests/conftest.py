import pytest


@pytest.fixture(autouse=True)
def _every_tool_registered_again():
    """A test may prune the live registry (main() applies ATLAS_MCP_TOOLSETS); the next test
    must start from the full set (#540)."""
    yield
    from mcp_server import server

    server._load(list(server._REGISTRY))
