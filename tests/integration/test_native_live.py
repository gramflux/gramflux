"""Explicit network opt-in; creates anonymous auth keys, never logs into an account."""

import os

import pytest

from gramflux.tools.native_probe import probe_native


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("GRAMFLUX_NATIVE_NETWORK") != "1", reason="native Telegram network probe is opt-in"
)
@pytest.mark.parametrize("mode", ["full", "intermediate", "abridged"])
async def test_native_real_key_and_encrypted_ping(mode):
    result = await probe_native(mode=mode)
    assert result["rsa_dh_confirmation"] is True
    assert result["encrypted_ping_pong"] is True
    assert result["account_login_attempted"] is False
    assert result["key_saved"] is False
