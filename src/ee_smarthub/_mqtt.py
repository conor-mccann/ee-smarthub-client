"""MQTT-over-WebSocket transport for USP communication with EE SmartHub routers."""

import asyncio
import logging
import ssl
import uuid
from collections.abc import Generator
from contextlib import contextmanager

import aiomqtt
from aiomqtt.exceptions import MqttConnectError

from ._usp import build_connect_record, response_msg_id
from .exceptions import AuthenticationError, CommunicationError, ProtocolError

DEFAULT_TIMEOUT = 10.0

_TOPIC_REQUEST = "/{serial}/usp/admin/request"
_TOPIC_RESPONSE = "/{serial}/usp/admin/response"
_USERNAME = "admin"
_WS_PATH = "/ws"

# CONNACK refusal reasons that mean "bad credentials".  paho-mqtt maps the
# MQTT 3.1.1 return codes 4 and 5 to the MQTT 5 reason codes 0x86 and 0x87.
_AUTH_REFUSAL_CODES = frozenset({0x86, 0x87})

logger = logging.getLogger(__name__)


async def check_credentials(
    hostname: str, password: str, *, timeout: float = DEFAULT_TIMEOUT
) -> None:
    """Connect and immediately disconnect to verify the router is reachable and password is correct.

    Raises AuthenticationError on bad credentials, CommunicationError on network failure.
    """
    with _translate_errors():
        async with _make_client(hostname, password, timeout):
            pass  # successful connect + auto-disconnect proves credentials


async def send_request(
    hostname: str,
    password: str,
    serial: str,
    request_payload: bytes,
    msg_id: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
) -> bytes:
    """Send a USP request over MQTT-over-WebSocket and return the raw response.

    Messages on the response topic whose USP ``msg_id`` differs from ``msg_id``
    (e.g. replies to another controller) are ignored.

    Raises CommunicationError, AuthenticationError, or ProtocolError on failure.
    """
    topic_request = _TOPIC_REQUEST.format(serial=serial)
    topic_response = _TOPIC_RESPONSE.format(serial=serial)

    logger.debug("Sending USP request to %s (timeout=%.1fs)", hostname, timeout)
    with _translate_errors():
        async with _make_client(hostname, password, timeout) as client:
            await client.subscribe(topic_response, qos=1)
            logger.debug("Subscribed to %s", topic_response)

            connect_record = build_connect_record(serial, topic_response)
            await client.publish(topic_request, payload=connect_record, qos=1)
            await client.publish(topic_request, payload=request_payload, qos=1)
            logger.debug("Published request to %s", topic_request)

            async with asyncio.timeout(timeout):
                async for message in client.messages:
                    if not isinstance(message.payload, bytes | bytearray):
                        continue
                    payload = bytes(message.payload)
                    if response_msg_id(payload) != msg_id:
                        logger.debug("Ignoring message with non-matching msg_id")
                        continue
                    logger.debug("Received response (%d bytes)", len(payload))
                    return payload

    raise ProtocolError("No response received from router")


def _create_insecure_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _make_client(hostname: str, password: str, timeout: float) -> aiomqtt.Client:
    """Create (but do not enter) an MQTT client for the router."""
    client_id = f"ee-smarthub-{uuid.uuid4().hex[:8]}"
    logger.debug("Creating MQTT client for %s (client_id=%s)", hostname, client_id)
    return aiomqtt.Client(
        hostname=hostname,
        port=443,
        username=_USERNAME,
        password=password,
        identifier=client_id,
        transport="websockets",
        tls_context=_create_insecure_ssl_context(),
        websocket_path=_WS_PATH,
        timeout=timeout,
    )


@contextmanager
def _translate_errors() -> Generator[None]:
    """Map aiomqtt / timeout errors onto the library's exception hierarchy."""
    try:
        yield
    except MqttConnectError as exc:
        code = getattr(exc.rc, "value", exc.rc)
        if code in _AUTH_REFUSAL_CODES:
            raise AuthenticationError(
                f"Router rejected MQTT connection: {exc}"
            ) from exc
        raise CommunicationError(f"MQTT connection refused: {exc}") from exc
    except aiomqtt.MqttError as exc:
        raise CommunicationError(f"MQTT communication failed: {exc}") from exc
    except TimeoutError as exc:
        raise CommunicationError("Timed out waiting for USP response") from exc
