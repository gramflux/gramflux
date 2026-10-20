import pytest

from gramflux import Client, Config
from gramflux.backend import map_rpc, rpc_error
from gramflux.errors import AuthenticationError, ConfigurationError, MigrationRequired, RPCError


@pytest.mark.parametrize(
    "kwargs",
    [
        {"request_timeout": 0},
        {"request_timeout": float("nan")},
        {"max_concurrent_requests": 0},
        {"event_queue_size": -1},
        {"reconnect_attempts": -1},
        {"transport": "bad"},
    ],
)
def test_configuration(kwargs):
    with pytest.raises(ConfigurationError):
        Config(**kwargs)


def test_credentials_and_error_redaction():
    for api_id, api_hash in [(0, "a" * 32), (1234, "SECRET")]:
        with pytest.raises(ConfigurationError):
            Client(api_id=api_id, api_hash=api_hash)
    assert str(RPCError(400, "my private contents")) == "Telegram RPC 400: RPC_ERROR"
    assert isinstance(map_rpc(rpc_error(400, "PHONE_CODE_INVALID")), AuthenticationError)
    mapped = map_rpc(rpc_error(303, f"PHONE_MIGRATE_{2}"))
    assert isinstance(mapped, MigrationRequired)
    assert mapped.dc == 2


def test_backend_log_redaction(caplog):
    from gramflux.backend import backend_logger

    logger = backend_logger()
    logger.error("request=%s", "TOP-SECRET-CREDENTIAL")
    assert "TOP-SECRET-CREDENTIAL" not in caplog.text
    assert "details suppressed" in caplog.text


def test_backend_does_not_use_last_resort_stderr():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from gramflux.backend import backend_logger; "
            'backend_logger().warning("sensitive backend warning")',
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout == result.stderr == ""


@pytest.mark.parametrize("kind", ["unauthorized", "flood", "server"])
async def test_authorization_check_does_not_hide_other_rpc_failures(kind):
    from gramflux.backend import is_authorized
    from gramflux.errors import FloodWait

    async def backend(request):
        if kind == "unauthorized":
            raise rpc_error(401, "AUTH_KEY_UNREGISTERED")
        if kind == "flood":
            raise rpc_error(420, f"FLOOD_WAIT_{30}")
        raise rpc_error(500, "INTERNAL")

    if kind == "unauthorized":
        assert not await is_authorized(backend)
    else:
        with pytest.raises(FloodWait if kind == "flood" else RPCError):
            await is_authorized(backend)
