"""Explicit credential-free Telegram initial-handshake check (not authentication)."""

import argparse
import asyncio
import json
from dataclasses import asdict

from gramflux.mtproto.probe import probe_datacenter


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="149.154.167.51")
    parser.add_argument("--port", type=int, default=443)
    args = parser.parse_args()

    async def run() -> None:
        results = {}
        for mode in ("full", "intermediate", "abridged"):
            result = await probe_datacenter(args.host, args.port, mode=mode)
            results[mode] = asdict(result)
        print(
            json.dumps(
                {
                    "host": args.host,
                    "port": args.port,
                    "scope": "unencrypted req_pq_multi only; no server authentication",
                    "results": results,
                },
                indent=2,
            )
        )

    asyncio.run(run())


if __name__ == "__main__":
    main()
