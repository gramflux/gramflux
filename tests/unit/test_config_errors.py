import pytest
from telethon import errors

from gramflux import Client, Config
from gramflux.backend import map_rpc
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
    assert isinstance(map_rpc(errors.PhoneCodeInvalidError(None)), AuthenticationError)
    mapped = map_rpc(errors.PhoneMigrateError(None, capture=2))
    assert isinstance(mapped, MigrationRequired)
    assert mapped.dc == 2


def test_backend_log_redaction(caplog):
    from gramflux.backend import backend_logger

    logger = backend_logger()
    logger.error("request=%s", "TOP-SECRET-CREDENTIAL")
    assert "TOP-SECRET-CREDENTIAL" not in caplog.text
    assert "details suppressed" in caplog.text
