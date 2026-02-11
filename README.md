# EE SmartHub Client

[![PyPI](https://img.shields.io/pypi/v/ee-smarthub)](https://pypi.org/project/ee-smarthub/)
[![Python](https://img.shields.io/pypi/pyversions/ee-smarthub)](https://pypi.org/project/ee-smarthub/)
[![License: MIT](https://img.shields.io/pypi/l/ee-smarthub)](https://github.com/conor-mccann/ee-smarthub-client/blob/main/LICENSE)

Python async client library for interacting with EE SmartHub routers using the USP protocol over MQTT WebSocket.

## Why This Library?

The EE SmartHub web interface is React-based and dynamically loads data via JavaScript, making traditional web scraping impractical. This library uses the router's native USP (User Services Platform) protocol providing:

- **Reliable data access** — won't break with UI changes
- **Efficient communication** — direct protocol access, not HTML parsing
- **Structured data** — clean, typed Python objects

## Installation

```bash
pip install ee-smarthub
```

## Usage

The client requires an `aiohttp.ClientSession`, allowing callers to manage session lifecycle.

```python
import asyncio
import aiohttp
from ee_smarthub import SmartHubClient

async def main():
    async with aiohttp.ClientSession() as session:
        client = SmartHubClient("192.168.1.1", "your-password", session)
        hosts = await client.get_hosts()
        for host in hosts:
            print(f"{host.name:30s} {host.ip_address:15s} {host.mac_address}")

asyncio.run(main())
```

### Validating Credentials

To check that the router is reachable and the password is correct without fetching device data:

```python
async with aiohttp.ClientSession() as session:
    client = SmartHubClient("192.168.1.1", "your-password", session)
    await client.validate_connection()  # raises on failure
```

This performs an HTTP fetch and MQTT connect/disconnect.

### Host Fields

Each `Host` object contains:

| Field                | Type             | Description                                          |
| -------------------- | ---------------- | ---------------------------------------------------- |
| `mac_address`        | `str`            | Physical (MAC) address                               |
| `ip_address`         | `str`            | IP address                                           |
| `hostname`           | `str`            | DHCP hostname                                        |
| `user_friendly_name` | `str`            | User-assigned name (BT vendor extension)             |
| `name`               | `str` (property) | Best available name (user-friendly > hostname > MAC) |
| `active`             | `bool`           | Currently connected                                  |
| `interface_type`     | `str`            | Connection type (e.g. "Wi-Fi", "Ethernet")           |
| `frequency_band`     | `str \| None`    | Wi-Fi band (e.g. "2.4GHz", "5GHz")                   |
| `bytes_sent`         | `int`            | Total bytes sent                                     |
| `bytes_received`     | `int`            | Total bytes received                                 |

## How It Works

The library implements the [User Services Platform (USP)](https://usp.technology/) protocol defined by the Broadband Forum:

1. Fetch serial number - HTTPS GET to `{ROUTER_URL}/config.json`
2. Connect to MQTT - WebSocket connection to router on port 443
3. Authenticate with router password
4. Send USP request - Protobuf-encoded Get request for `Device.Hosts.Host.*`
5. Parse response - Extract device parameters from protobuf response
6. Disconnect - Close connection (short-lived connection model)

The connection is short-lived by design - simple, reliable, and efficient for typical polling intervals.

## Development

### Regenerating Protobuf Code

If the USP protocol specification is updated, regenerate the Python protobuf code:

```bash
./scripts/generate_proto.sh
```

This downloads the latest `.proto` files from the Broadband Forum repository and generates Python code using `betterproto` into `src/ee_smarthub/proto/`.

## Security Considerations

The EE SmartHub uses a self-signed SSL certificate. This library disables certificate verification for HTTPS and WebSocket connections to communicate with the router, which means TLS connections are not fully verified.

Since the router is on your local network, exposure is limited. Ensure your local network is secure.

## Compatibility

- Python: 3.11+
- Router: EE SmartHub
- Protocol: USP

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Resources

- [USP Technology](https://usp.technology/)
- [CWMP Data Models](https://cwmp-data-models.broadband-forum.org/)
- [Broadband Forum USP](https://github.com/BroadbandForum/usp)

---

**Note:** This is an unofficial client library and is not affiliated with or endorsed by EE Limited.
