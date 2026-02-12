"""High-level async client for querying EE SmartHub routers."""

import logging

import aiohttp

from ._mqtt import AGENT_ID_PREFIX, CONTROLLER_ID, send_request, test_credentials
from ._usp import build_get_request, parse_get_response
from .exceptions import CommunicationError, ProtocolError
from .models import Host

_HOST_PATH = "Device.Hosts.Host."

logger = logging.getLogger(__name__)


class SmartHubClient:
    """Async client for querying an EE SmartHub router via USP over MQTT."""

    def __init__(
        self, hostname: str, password: str, session: aiohttp.ClientSession
    ) -> None:
        """Initialise the client.

        Args:
            hostname: Router IP address or hostname (e.g. "192.168.1.1").
            password: The admin password for the router.
            session: A caller-managed aiohttp session.  The client does not
                close this session; the caller is responsible for its lifecycle.
        """
        self._hostname = hostname
        self._password = password
        self._session = session
        self._serial: str | None = None

    async def _fetch_serial(self) -> str:
        """Fetch the router serial number, caching it for subsequent calls."""
        if self._serial is not None:
            return self._serial

        url = f"https://{self._hostname}/config.json"
        logger.debug(f"Fetching serial number from {url}")
        try:
            async with self._session.get(url, ssl=False) as resp:
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
        self._serial = serial
        logger.debug(f"Router serial number: {serial}")
        return serial

    async def validate_connection(self) -> None:
        """Verify that the router is reachable and credentials are valid."""
        logger.debug(f"Validating connection to {self._hostname}")
        await self._fetch_serial()
        await test_credentials(self._hostname, self._password)
        logger.debug(f"Connection to {self._hostname} validated successfully")

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
        hosts = parse_get_response(response)
        logger.debug(f"Fetched {len(hosts)} host(s) from router")
        return hosts
