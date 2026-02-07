from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from ee_smarthub._mqtt import AGENT_ID_PREFIX, CONTROLLER_ID
from ee_smarthub.client import SmartHubClient
from ee_smarthub.exceptions import ConnectionError, ProtocolError
from ee_smarthub.models import Host

_SERIAL = "CP2231TEST"


def _mock_response(*, json_data=None, status=200, json_error=None):
    """Create a mock aiohttp response context manager."""
    mock_resp = AsyncMock()
    mock_resp.status = status
    if json_error:
        mock_resp.json = AsyncMock(side_effect=json_error)
    else:
        mock_resp.json = AsyncMock(return_value=json_data)
    mock_resp.raise_for_status = MagicMock()
    if status >= 400:
        mock_resp.raise_for_status = MagicMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=MagicMock(), history=(), status=status
            )
        )
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)
    return mock_resp


def _mock_session(mock_resp=None, *, get_error=None):
    """Create a mock aiohttp session context manager."""
    mock = MagicMock()
    if get_error:
        mock.get = MagicMock(side_effect=get_error)
    else:
        mock.get = MagicMock(return_value=mock_resp)
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


@pytest.mark.asyncio
async def test_get_hosts():
    raw_response = b"\x01\x02\x03"
    expected_hosts = [Host(mac_address="AA:BB:CC:DD:EE:FF", name="phone", ip_address="192.168.1.10")]

    client = SmartHubClient("192.168.1.1", "secret")

    with (
        patch.object(client, "_fetch_serial", new_callable=AsyncMock, return_value=_SERIAL),
        patch("ee_smarthub.client.send_request", new_callable=AsyncMock, return_value=raw_response) as mock_send,
        patch("ee_smarthub.client.build_get_request", return_value=b"\xaa\xbb") as mock_build,
        patch("ee_smarthub.client.parse_get_response", return_value=expected_hosts) as mock_parse,
    ):
        hosts = await client.get_hosts()

    assert hosts == expected_hosts

    agent_id = AGENT_ID_PREFIX + _SERIAL
    mock_build.assert_called_once_with(
        to_id=agent_id, from_id=CONTROLLER_ID, path="Device.Hosts.Host."
    )
    mock_send.assert_called_once_with("192.168.1.1", "secret", _SERIAL, b"\xaa\xbb")
    mock_parse.assert_called_once_with(raw_response)


@pytest.mark.asyncio
async def test_fetch_serial():
    resp = _mock_response(json_data={"SerialNumber": _SERIAL})
    session = _mock_session(resp)

    with patch("ee_smarthub.client.aiohttp.ClientSession", return_value=session):
        client = SmartHubClient("192.168.1.1", "secret")
        serial = await client._fetch_serial()

    assert serial == _SERIAL
    session.get.assert_called_once_with("https://192.168.1.1/config.json", ssl=False)


@pytest.mark.asyncio
async def test_fetch_serial_http_error():
    session = _mock_session(get_error=aiohttp.ClientError("Connection refused"))

    with patch("ee_smarthub.client.aiohttp.ClientSession", return_value=session):
        client = SmartHubClient("192.168.1.1", "secret")
        with pytest.raises(ConnectionError, match="Failed to fetch serial number"):
            await client._fetch_serial()


@pytest.mark.asyncio
async def test_fetch_serial_http_status_error():
    resp = _mock_response(status=404)
    session = _mock_session(resp)

    with patch("ee_smarthub.client.aiohttp.ClientSession", return_value=session):
        client = SmartHubClient("192.168.1.1", "secret")
        with pytest.raises(ConnectionError, match="Failed to fetch serial number"):
            await client._fetch_serial()


@pytest.mark.asyncio
async def test_fetch_serial_invalid_json():
    resp = _mock_response(json_error=ValueError("No JSON"))
    session = _mock_session(resp)

    with patch("ee_smarthub.client.aiohttp.ClientSession", return_value=session):
        client = SmartHubClient("192.168.1.1", "secret")
        with pytest.raises(ProtocolError, match="Invalid JSON response"):
            await client._fetch_serial()


@pytest.mark.asyncio
async def test_fetch_serial_missing_serial():
    resp = _mock_response(json_data={"SomeOtherKey": "value"})
    session = _mock_session(resp)

    with patch("ee_smarthub.client.aiohttp.ClientSession", return_value=session):
        client = SmartHubClient("192.168.1.1", "secret")
        with pytest.raises(ProtocolError, match="SerialNumber missing"):
            await client._fetch_serial()
