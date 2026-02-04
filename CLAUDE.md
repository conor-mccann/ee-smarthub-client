# CLAUDE.md

## Overview

Python async client library for interacting with EE SmartHub routers using the USP (User Services Platform) protocol over MQTT WebSocket. The library provides structured access to router data without relying on web scraping.

## Installation

```bash
pip install -e ".[dev]"
```

## Source Layout

```
src/ee_smarthub/
├── __init__.py          # Public API re-exports (done last)
├── client.py            # SmartHubClient — main entry point
├── exceptions.py        # Custom exception hierarchy
├── models.py            # Output dataclasses (e.g. Host)
├── _mqtt.py             # WebSocket + MQTT connection (private)
├── _usp.py              # USP protobuf encoding/decoding (private)
└── proto/               # Generated — do not edit
```

Files prefixed with `_` are internal. The public API surface is `client.py`, `models.py`, and `exceptions.py`.

## Protocol Flow

The library uses a short-lived connection model — open, fetch, close. No persistent connection, no heartbeats, no reconnection logic.

1. **Serial Number Fetch**: HTTPS GET to `{ROUTER_URL}/config.json`
2. **MQTT Connection**: WebSocket connection to router on port 443
3. **Authentication**: Authenticate with router password
4. **USP Request**: Send protobuf-encoded Get request for `Device.Hosts.Host.*`
5. **Response Parsing**: Extract device parameters from protobuf response
6. **Disconnect**: Close connection immediately after response

## Key Decisions

- **Host model is intentionally minimal** (`name`, `ip_address`, `mac_address`). Expand fields in `_usp.py` based on what the actual USP `GetResp` returns — do not add fields speculatively.
- **Self-signed certificates**: The router uses self-signed SSL. Certificate verification is intentionally disabled for both HTTPS and WebSocket connections.
- **Proto regeneration**: Run `./scripts/generate_proto.sh` to regenerate code in `proto/` from the Broadband Forum USP spec. Do not hand-edit anything in `proto/`.

## Resources

- [USP Technology](https://usp.technology/)
- [CWMP Data Models](https://cwmp-data-models.broadband-forum.org/)
- [Broadband Forum USP GitHub](https://github.com/BroadbandForum/usp)
