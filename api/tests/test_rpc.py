import pytest

from sigil.rpc import ChainError, RpcReader


@pytest.mark.asyncio
async def test_rpc_connection_failure_becomes_chain_error():
    reader = RpcReader("http://127.0.0.1:1", "A1JYKRSENgPY1Zqa9GjT41m4LuyqMv9dgqeNQ6bSh6HF", 0)
    with pytest.raises(ChainError):
        await reader.issuer("11111111111111111111111111111111")
