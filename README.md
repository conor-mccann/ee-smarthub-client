# EE SmartHub Client

Python async client library for interacting with EE SmartHub routers using the USP protocol over MQTT WebSocket.

## Why This Library?

The EE SmartHub web interface is React-based and dynamically loads data via JavaScript, making traditional web scraping impractical. This library uses the router's native USP (User Services Platform) protocol providing:

- **Reliable data access** - Won't break with UI changes
- **Efficient communication** - Direct protocol access, not HTML parsing
- **Structured data** - Clean, typed Python objects

## Installation

Not yet published to PyPI. Install from source:

```bash
git clone https://github.com/conor-mccann/ee-smarthub-client.git
cd ee-smarthub-client
pip install -e ".[dev]"
```

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
