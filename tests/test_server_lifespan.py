from charles_mcp.config import Config
from charles_mcp.server import create_server


def test_create_server_registers_public_lifespan() -> None:
    server = create_server(Config())

    assert server.settings.lifespan is not None
