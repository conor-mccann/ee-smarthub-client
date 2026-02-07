import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import aiomqtt
import pytest

from ee_smarthub._mqtt import (
    AGENT_ID_PREFIX,
    CONTROLLER_ID,
    _build_connect_record,
    send_request,
)
from ee_smarthub.exceptions import AuthenticationError, CommunicationError
from ee_smarthub.proto.usp_record import Record

_PATCH_TARGET = "ee_smarthub._mqtt.aiomqtt.Client"


async def _one_message(payload: bytes):
    yield MagicMock(payload=payload)


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
    response = b"\x01\x02\x03"
    request = b"\x04\x05\x06"
    serial = "CP2231TEST"
    mock = _mock_client(_one_message(response))

    with patch(_PATCH_TARGET, return_value=mock):
        result = await send_request(
            hostname="192.168.1.1",
            password="secret",
            serial=serial,
            request_payload=request,
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
async def test_send_request_auth_error():
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(
        side_effect=aiomqtt.MqttCodeError(4, "Bad username or password"),
    )
    mock.__aexit__ = AsyncMock(return_value=False)

    with patch(_PATCH_TARGET, return_value=mock):
        with pytest.raises(AuthenticationError, match="Router rejected MQTT connection"):
            await send_request(
                hostname="192.168.1.1",
                password="wrong",
                serial="ABC123",
                request_payload=b"",
            )


@pytest.mark.asyncio
async def test_send_request_connection_error():
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(side_effect=aiomqtt.MqttError("Connection refused"))
    mock.__aexit__ = AsyncMock(return_value=False)

    with patch(_PATCH_TARGET, return_value=mock):
        with pytest.raises(CommunicationError, match="MQTT communication failed"):
            await send_request(
                hostname="192.168.1.1",
                password="pass",
                serial="ABC123",
                request_payload=b"",
            )


@pytest.mark.asyncio
async def test_send_request_timeout():
    mock = _mock_client(_hang_forever())

    with patch(_PATCH_TARGET, return_value=mock):
        with pytest.raises(CommunicationError, match="Timed out"):
            await send_request(
                hostname="192.168.1.1",
                password="pass",
                serial="ABC123",
                request_payload=b"",
                timeout=0.05,
            )


def test_build_connect_record():
    agent_id = "os::012345-SERIAL123"
    topic = "/SERIAL123/usp/admin/response"

    data = _build_connect_record(agent_id, topic)
    record = Record().parse(data)

    assert record.to_id == agent_id
    assert record.from_id == CONTROLLER_ID
    assert record.mqtt_connect is not None
    assert record.mqtt_connect.subscribed_topic == topic
