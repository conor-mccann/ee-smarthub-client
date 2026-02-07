import aiohttp

from ._mqtt import AGENT_ID_PREFIX, CONTROLLER_ID, send_request
from ._usp import build_get_request, parse_get_response
from .exceptions import CommunicationError, ProtocolError
from .models import Host

_HOST_PATH = "Device.Hosts.Host."


class SmartHubClient:
    """Async client for querying an EE SmartHub router via USP over MQTT."""

    def __init__(self, hostname: str, password: str) -> None:
        self._hostname = hostname
        self._password = password

    async def _fetch_serial(self) -> str:
        """Fetch the router serial number from its config endpoint."""
        url = f"https://{self._hostname}/config.json"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, ssl=False) as resp:
                    resp.raise_for_status()
                    data = await resp.json(content_type=None)
        except aiohttp.ClientError as exc:
            raise CommunicationError(
                f"Failed to fetch serial number from {url}: {exc}"
            ) from exc
        except (ValueError, AttributeError) as exc:
            raise ProtocolError(
                f"Invalid JSON response from {url}: {exc}"
            ) from exc

        serial = data.get("SerialNumber")
        if not serial:
            raise ProtocolError("SerialNumber missing from config.json response")
        return serial

    async def get_hosts(self) -> list[Host]:
        """Fetch the list of connected hosts from the router."""
        serial = await self._fetch_serial()
        agent_id = AGENT_ID_PREFIX + serial
        request = build_get_request(
            to_id=agent_id, from_id=CONTROLLER_ID, path=_HOST_PATH
        )
        response = await send_request(
            self._hostname, self._password, serial, request
        )
        return parse_get_response(response)
