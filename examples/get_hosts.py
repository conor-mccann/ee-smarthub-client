"""Fetch connected hosts from an EE SmartHub router.

Usage:
    python examples/get_hosts.py <router-ip> <password>

Example:
    python examples/get_hosts.py 192.168.1.1 mypassword
"""

import asyncio
import sys

import aiohttp

from ee_smarthub import SmartHubClient


async def main(hostname: str, password: str) -> None:
    async with aiohttp.ClientSession() as session:
        client = SmartHubClient(hostname, password, session)
        hosts = await client.get_hosts()

        if not hosts:
            print("No hosts found.")
            return

        active = [h for h in hosts if h.active]
        print(f"{len(active)} active / {len(hosts)} total hosts\n")
        print(f"{'Name':30s} {'IP Address':15s} {'MAC Address':18s} {'Type':8s} {'Band'}")
        print("-" * 85)
        for h in active:
            print(f"{h.name:30s} {h.ip_address:15s} {h.mac_address:18s} {h.interface_type:8s} {h.frequency_band or ''}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__.strip())
        sys.exit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2]))
