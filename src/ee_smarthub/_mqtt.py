import asyncio
import ssl
import uuid

import aiomqtt

from .exceptions import AuthenticationError, ConnectionError, ProtocolError
from .proto.usp_record import (
    MqttConnectRecord,
    MqttConnectRecordMqttVersion,
    Record,
    RecordPayloadSecurity,
)

CONTROLLER_ID = "usp-gui-admin"
AGENT_ID_PREFIX = "os::012345-"

_TOPIC_REQUEST = "/{serial}/usp/admin/request"
_TOPIC_REPLY = "/{serial}/usp/admin/reply-to/{client_id}"
_USERNAME = "admin"
_WS_PATH = "/ws"


def _create_insecure_ssl_context() -> ssl.SSLContext:
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _build_connect_record(agent_id: str, subscribe_topic: str) -> bytes:
    """Build the USP MqttConnectRecord that tells the Agent our reply topic."""
    mqtt_connect = MqttConnectRecord(
        version=MqttConnectRecordMqttVersion.V3_1_1,
        subscribed_topic=subscribe_topic,
    )
    record = Record(
        version="1.4",
        to_id=agent_id,
        from_id=CONTROLLER_ID,
        payload_security=RecordPayloadSecurity.PLAINTEXT,
        mqtt_connect=mqtt_connect,
    )
    return bytes(record)


async def send_request(
    hostname: str,
    password: str,
    serial: str,
    request_payload: bytes,
    *,
    timeout: float = 10.0,
) -> bytes:
    """Send a USP request over MQTT-over-WebSocket and return the raw response.

    Raises ConnectionError, AuthenticationError, or ProtocolError on failure.
    """
    ssl_ctx = _create_insecure_ssl_context()
    client_id = f"ee-smarthub-{uuid.uuid4().hex[:8]}"
    agent_id = AGENT_ID_PREFIX + serial
    topic_request = _TOPIC_REQUEST.format(serial=serial)
    topic_reply = _TOPIC_REPLY.format(serial=serial, client_id=client_id)

    try:
        async with aiomqtt.Client(
            hostname=hostname,
            port=443,
            username=_USERNAME,
            password=password,
            identifier=client_id,
            transport="websockets",
            tls_context=ssl_ctx,
            websocket_path=_WS_PATH,
        ) as client:
            await client.subscribe(topic_reply, qos=1)

            connect_record = _build_connect_record(agent_id, topic_reply)
            await client.publish(topic_request, payload=connect_record, qos=1)

            await client.publish(topic_request, payload=request_payload, qos=1)

            async with asyncio.timeout(timeout):
                async for message in client.messages:
                    return bytes(message.payload)

    except aiomqtt.MqttCodeError as exc:
        raise AuthenticationError(
            f"Router rejected MQTT connection: {exc}"
        ) from exc
    except aiomqtt.MqttError as exc:
        raise ConnectionError(f"MQTT communication failed: {exc}") from exc
    except TimeoutError as exc:
        raise ConnectionError("Timed out waiting for USP response") from exc

    raise ProtocolError("No response received from router")
