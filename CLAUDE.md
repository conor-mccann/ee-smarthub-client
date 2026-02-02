# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Python async client library for interacting with EE SmartHub routers using the USP (User Services Platform) protocol over MQTT WebSocket. The library provides structured access to router data without relying on web scraping.

## Installation & Setup

Install from source with development dependencies:
```bash
pip install -e ".[dev]"
```

## Key Architecture

### Protocol Flow
The library implements a short-lived connection model using the USP protocol:

1. **Serial Number Fetch**: HTTPS GET to `{ROUTER_URL}/config.json`
2. **MQTT Connection**: WebSocket connection to router on port 443
3. **Authentication**: Authenticate with router password
4. **USP Request**: Send protobuf-encoded Get request for `Device.Hosts.Host.*`
5. **Response Parsing**: Extract device parameters from protobuf response
6. **Disconnect**: Close connection immediately after response

This short-lived approach is intentional - the connection is opened, data is fetched, and then closed. This is efficient for typical polling intervals and keeps the implementation simple.

### Protobuf Code Generation

The library uses protobuf for USP protocol communication. Code is generated in `src/ee_smarthub/proto/` using `betterproto`.

To regenerate protobuf code when the USP specification is updated:
```bash
./scripts/generate_proto.sh
```

This script:
- Downloads latest `.proto` files from Broadband Forum repository
- Generates Python code using betterproto
- Outputs to `src/ee_smarthub/proto/`

### Security Model

The EE SmartHub uses self-signed SSL certificates. The library disables certificate verification for both HTTPS and WebSocket connections to communicate with the router. This means TLS connections are not fully verified.

When implementing or modifying connection code:
- Expect self-signed certificates on local network routers
- Certificate verification is intentionally disabled
- Document any security-related changes clearly

## Technical Constraints

- **Python Version**: 3.11+ required
- **Target Router**: EE SmartHub
- **Protocol**: USP (User Services Platform) from Broadband Forum
- **Connection Type**: Async MQTT over WebSocket
- **Certificate Handling**: Self-signed certificates accepted (local network trust model)

## Resources

- [USP Technology](https://usp.technology/)
- [CWMP Data Models](https://cwmp-data-models.broadband-forum.org/)
- [Broadband Forum USP GitHub](https://github.com/BroadbandForum/usp)
