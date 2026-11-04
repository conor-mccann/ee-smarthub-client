import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiomqtt
import pytest
from aiomqtt.exceptions import MqttConnectError
from paho.mqtt.client import convert_connack_rc_to_reason_code
from paho.mqtt.enums import ConnackCode

from ee_smarthub._mqtt import check_credentials, send_request
from ee_smarthub._usp import AGENT_ID_PREFIX, CONTROLLER_ID, build_get_request
from ee_smarthub.exceptions import (
    AuthenticationError,
    CommunicationError,
    ProtocolError,
)
from ee_smarthub.proto.usp_record import Record

_PATCH_TARGET = "ee_smarthub._mqtt.aiomqtt.Client"


async def _messages(*payloads: bytes):
    for payload in payloads:
        yield MagicMock(payload=payload)


def _connack_error(code: int) -> MqttConnectError:
    return MqttConnectError(convert_connack_rc_to_reason_code(ConnackCode(code)))


async def _hang_forever():
    await asyncio.sleep(999)
    yield


def _mock_client(messages) -> MagicMock:
    mock = MagicMock()
    mock.subscribe = AsyncMock()
    mock.publish = AsyncMock()
    mock.messages = messages
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


@pytest.mark.asyncio
async def test_send_request_message_sequence():
    serial = "CP2231TEST"
    msg_id, request = build_get_request(serial, "Device.Hosts.Host.")
    # Any Record carrying our msg_id counts as the response.
    response = request
    mock = _mock_client(_messages(response))

    with patch(_PATCH_TARGET, return_value=mock):
        result = await send_request(
            hostname="192.168.1.1",
            password="secret",
            serial=serial,
            request_payload=request,
            msg_id=msg_id,
        )

    assert result == response

    mock.subscribe.assert_called_once()
    subscribe_topic = mock.subscribe.call_args[0][0]
    assert serial in subscribe_topic
    assert "response" in subscribe_topic

    assert mock.publish.call_count == 2
    first_call, second_call = mock.publish.call_args_list

    first_topic = first_call[0][0]
    first_payload = first_call[1]["payload"]
    assert serial in first_topic
    assert "request" in first_topic

    record = Record().parse(first_payload)
    assert record.to_id == AGENT_ID_PREFIX + serial
    assert record.from_id == CONTROLLER_ID
    assert record.mqtt_connect is not None

    assert second_call[1]["payload"] == request


@pytest.mark.asyncio
async def test_send_request_skips_non_matching_messages():
    serial = "CP2231TEST"
    msg_id, request = build_get_request(serial, "Device.Hosts.Host.")
    other_id, other = build_get_request(serial, "Device.Hosts.Host.")
    assert other_id != msg_id
    mock = _mock_client(_messages(b"garbage", other, request))

    with patch(_PATCH_TARGET, return_value=mock):
        result = await send_request(
            "192.168.1.1", "secret", serial, request, msg_id
        )

    assert result == request


@pytest.mark.asyncio
async def test_send_request_no_matching_message_before_stream_ends():
    serial = "CP2231TEST"
    msg_id, request = build_get_request(serial, "Device.Hosts.Host.")
    _, other = build_get_request(serial, "Device.Hosts.Host.")
    mock = _mock_client(_messages(other))

    with patch(_PATCH_TARGET, return_value=mock):
        with pytest.raises(ProtocolError, match="No response"):
            await send_request("192.168.1.1", "secret", serial, request, msg_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [4, 5])
async def test_send_request_auth_error(code):
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(side_effect=_connack_error(code))
    mock.__aexit__ = AsyncMock(return_value=False)

    with patch(_PATCH_TARGET, return_value=mock):
        with pytest.raises(AuthenticationError, match="Router rejected MQTT connection"):
            await send_request("192.168.1.1", "wrong", "ABC123", b"", "id")


@pytest.mark.asyncio
async def test_send_request_server_unavailable_is_not_auth_error():
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(side_effect=_connack_error(3))
    mock.__aexit__ = AsyncMock(return_value=False)

    with patch(_PATCH_TARGET, return_value=mock):
        with pytest.raises(CommunicationError, match="connection refused"):
            await send_request("192.168.1.1", "pass", "ABC123", b"", "id")


@pytest.mark.asyncio
async def test_send_request_generic_code_error_is_communication_error():
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(
        side_effect=aiomqtt.MqttCodeError(1, "Could not subscribe to topic"),
    )
    mock.__aexit__ = AsyncMock(return_value=False)

    with patch(_PATCH_TARGET, return_value=mock):
        with pytest.raises(CommunicationError, match="MQTT communication failed"):
            await send_request("192.168.1.1", "pass", "ABC123", b"", "id")


@pytest.mark.asyncio
async def test_send_request_connection_error():
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(side_effect=aiomqtt.MqttError("Connection refused"))
    mock.__aexit__ = AsyncMock(return_value=False)

    with patch(_PATCH_TARGET, return_value=mock):
        with pytest.raises(CommunicationError, match="MQTT communication failed"):
            await send_request("192.168.1.1", "pass", "ABC123", b"", "id")


@pytest.mark.asyncio
async def test_send_request_timeout():
    mock = _mock_client(_hang_forever())

    with patch(_PATCH_TARGET, return_value=mock):
        with pytest.raises(CommunicationError, match="Timed out"):
            await send_request(
                "192.168.1.1", "pass", "ABC123", b"", "id", timeout=0.05
            )


@pytest.mark.asyncio
async def test_check_credentials_success():
    mock = _mock_client(_messages())

    with patch(_PATCH_TARGET, return_value=mock) as mock_cls:
        await check_credentials("192.168.1.1", "secret", timeout=4.0)

    assert mock_cls.call_args.kwargs["password"] == "secret"
    assert mock_cls.call_args.kwargs["timeout"] == 4.0


@pytest.mark.asyncio
async def test_check_credentials_bad_password():
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(side_effect=_connack_error(4))
    mock.__aexit__ = AsyncMock(return_value=False)

    with patch(_PATCH_TARGET, return_value=mock):
        with pytest.raises(AuthenticationError):
            await check_credentials("192.168.1.1", "wrong")


@pytest.mark.asyncio
async def test_check_credentials_network_error():
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(side_effect=aiomqtt.MqttError("unreachable"))
    mock.__aexit__ = AsyncMock(return_value=False)

    with patch(_PATCH_TARGET, return_value=mock):
        with pytest.raises(CommunicationError):
            await check_credentials("192.168.1.1", "pw")
