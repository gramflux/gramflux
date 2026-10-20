"""Read-only account test, disabled unless the tester explicitly opts in."""

import os

import pytest

from gramflux import Client


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("GRAMFLUX_LIVE") != "1",
    reason="requires explicit live opt-in and authorized GramFlux session",
)
async def test_live_identity():
    async with Client(
        os.environ["GRAMFLUX_SESSION"],
        api_id=int(os.environ["GRAMFLUX_API_ID"]),
        api_hash=os.environ["GRAMFLUX_API_HASH"],
    ) as client:
        assert await client.is_authorized()
        assert (await client.get_me()).id > 0
