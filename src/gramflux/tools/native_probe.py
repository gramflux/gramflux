"""Opt-in real RSA/DH and encrypted MTProto probe, with no account credentials."""

import argparse
import asyncio
import json
import secrets
import time
from typing import Any, Literal

from gramflux.errors import RPCError, SerializationError, TransportError
from gramflux.mtproto import protocol
from gramflux.mtproto.auth_key import create_key
from gramflux.mtproto.connection import Connection
from gramflux.mtproto.sender import Sender
from gramflux.raw import functions


async def probe_native(
    *,
    host: str = "149.154.167.51",
    port: int = 443,
    dc_id: int = 2,
    mode: Literal["full", "intermediate", "abridged"] = "intermediate",
    deadline: float = 30,
) -> dict[str, Any]:
    connection = Connection(host, port, mode)
    sender: Sender | None = None
    start = time.perf_counter()
    async with asyncio.timeout(deadline):
        try:
            await connection.connect()
            auth = await create_key(connection, dc_id)
            sender = Sender(connection, auth.key, auth.salt, time_offset=auth.time_offset)
            sender.start()
            ping = secrets.randbits(63)
            pong = await sender.invoke(
                protocol.object("ping", ping_id=ping), deadline_seconds=deadline
            )
            if pong.definition.name != "pong" or pong.ping_id != ping:
                raise SerializationError("encrypted native pong did not match the probe")
            result = {
                "host": host,
                "mode": mode,
                "rsa_dh_confirmation": True,
                "encrypted_ping_pong": True,
                "account_login_attempted": False,
                "key_saved": False,
            }
            try:
                nearest = await sender.invoke(
                    functions.help.GetNearestDcRequest(), deadline_seconds=deadline
                )
            except RPCError as error:
                result["api_probe_rpc_error"] = error.name
            else:
                if nearest.definition.name != "nearestDc":
                    raise SerializationError("unexpected anonymous API response")
                result["anonymous_api_constructor"] = nearest.definition.name
                result["nearest_dc"] = nearest.nearest_dc
            try:
                destroyed = await sender.invoke(
                    protocol.object("destroy_auth_key"), deadline_seconds=5
                )
            except (TransportError, TimeoutError):
                # EOF is an ambiguous cleanup outcome, never proof of key destruction.
                result["anonymous_key_destroyed"] = None
                result["key_cleanup_status"] = "unconfirmed_connection_closed_or_timed_out"
            else:
                result["anonymous_key_destroyed"] = (
                    destroyed.definition.name == "destroy_auth_key_ok"
                )
                result["key_cleanup_status"] = destroyed.definition.name
            result["elapsed_seconds"] = time.perf_counter() - start
            return result
        finally:
            if sender is not None:
                await sender.close()
            else:
                await connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=["full", "intermediate", "abridged"], default="intermediate"
    )
    parser.add_argument("--host", default="149.154.167.51")
    parser.add_argument("--port", type=int, default=443)
    parser.add_argument("--dc-id", type=int, default=2)
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(
                probe_native(host=args.host, port=args.port, dc_id=args.dc_id, mode=args.mode)
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
