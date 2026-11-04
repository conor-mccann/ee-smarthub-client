"""High-level async client for querying EE SmartHub routers."""

import logging

import aiohttp

from ._mqtt import DEFAULT_TIMEOUT, check_credentials, send_request
from ._usp import HOST_PATH, build_get_request, parse_get_response
from .exceptions import CommunicationError, ProtocolError
from .models import Host

logger = logging.getLogger(__name__)


class SmartHubClient:
    """Async client for querying an EE SmartHub router via USP over MQTT."""

    def __init__(
        self,
        hostname: str,
        password: str,
        session: aiohttp.ClientSession,
        *,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialise the client.

        Args:
            hostname: Router IP address or hostname (e.g. "192.168.1.1").
            password: The admin password for the router.
            session: A caller-managed aiohttp session.  The client does not
                close this session; the caller is responsible for its lifecycle.
            timeout: Seconds to wait for each network operation (the HTTP
                fetch of the serial number and each MQTT exchange).
        """
        self._hostname = hostname
        self._password = password
        self._session = session
        self._timeout = timeout
        self._serial: str | None = None

    async def validate_connection(self) -> str:
        """Verify that the router is reachable and credentials are valid.

        Returns:
            The router's serial number.
        """
        logger.debug("Validating connection to %s", self._hostname)
        serial = await self._fetch_serial()
        await check_credentials(self._hostname, self._password, timeout=self._timeout)
        logger.debug("Connection to %s validated successfully", self._hostname)
        return serial

    async def get_hosts(self) -> list[Host]:
        """Fetch the list of connected hosts from the router."""
        serial = await self._fetch_serial()
        msg_id, request = build_get_request(serial, HOST_PATH)
        response = await send_request(
            self._hostname,
            self._password,
            serial,
            request,
            msg_id,
            timeout=self._timeout,
        )
        hosts = parse_get_response(response)
        logger.debug("Fetched %d host(s) from router", len(hosts))
        return hosts

    async def _fetch_serial(self) -> str:
        """Fetch the router serial number, caching it for subsequent calls."""
        if self._serial is not None:
            return self._serial

        url = f"https://{self._hostname}/config.json"
        logger.debug("Fetching serial number from %s", url)
        try:
            async with self._session.get(
                url, ssl=False, timeout=aiohttp.ClientTimeout(total=self._timeout)
            ) as resp:
                resp.raise_for_status()
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise CommunicationError(
                f"Failed to fetch serial number from {url}: {exc!r}"
            ) from exc
        except ValueError as exc:
            raise ProtocolError(f"Invalid JSON response from {url}: {exc}") from exc

        if not isinstance(data, dict):
            raise ProtocolError(
                f"Unexpected config.json format from {url}: expected a JSON object"
            )
        serial = data.get("SerialNumber")
        if not serial:
            raise ProtocolError("SerialNumber missing from config.json response")
        self._serial = serial
        logger.debug("Router serial number: %s", serial)
        return serial
