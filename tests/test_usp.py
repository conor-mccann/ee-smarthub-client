import pytest

from ee_smarthub._usp import (
    _extract_frequency,
    _params_to_host,
    _safe_int,
    build_get_request,
    parse_get_response,
)
from ee_smarthub.exceptions import ProtocolError
from ee_smarthub.models import Host
from ee_smarthub.proto.usp import (
    Body,
    Error,
    GetResp,
    GetRespRequestedPathResult,
    GetRespResolvedPathResult,
    Header,
    HeaderMsgType,
    Msg,
    Response,
)
from ee_smarthub.proto.usp_record import (
    NoSessionContextRecord,
    Record,
    RecordPayloadSecurity,
)


def _build_response_bytes(
    path_results: list[GetRespRequestedPathResult],
) -> bytes:
    """Build a complete Record-framed USP GetResp from path results."""
    get_resp = GetResp(req_path_results=path_results)
    response = Response(get_resp=get_resp)
    body = Body(response=response)
    header = Header(msg_id="test-1", msg_type=HeaderMsgType.GET_RESP)
    msg = Msg(header=header, body=body)
    msg_bytes = bytes(msg)
    record = Record(
        version="1.4",
        to_id="controller",
        from_id="agent",
        payload_security=RecordPayloadSecurity.PLAINTEXT,
        no_session_context=NoSessionContextRecord(payload=msg_bytes),
    )
    return bytes(record)


def _host_path_result(
    index: int, params: dict[str, str], sub_path: str = ""
) -> GetRespResolvedPathResult:
    """Build a resolved path result for a single host."""
    path = f"Device.Hosts.Host.{index}.{sub_path}"
    return GetRespResolvedPathResult(resolved_path=path, result_params=params)


# --- _safe_int ---


def test_safe_int_valid():
    assert _safe_int("42") == 42


def test_safe_int_zero():
    assert _safe_int("0") == 0


def test_safe_int_empty_string():
    assert _safe_int("") == 0


def test_safe_int_non_numeric():
    assert _safe_int("abc") == 0


def test_safe_int_none():
    assert _safe_int(None) == 0  # type: ignore[arg-type]


# --- _extract_frequency ---


def test_extract_frequency_2_4ghz():
    assert _extract_frequency("Device.WiFi.Radio.1.Interface") == "2.4GHz"


def test_extract_frequency_5ghz():
    assert _extract_frequency("Device.WiFi.Radio.2.Interface") == "5GHz"


def test_extract_frequency_6ghz():
    assert _extract_frequency("Device.WiFi.Radio.3.Interface") == "6GHz"


def test_extract_frequency_ethernet():
    assert _extract_frequency("Device.Ethernet.Interface.1") is None


def test_extract_frequency_empty():
    assert _extract_frequency("") is None


# --- _params_to_host ---


def test_params_to_host_full():
    params = {
        "PhysAddress": "AA:BB:CC:DD:EE:FF",
        "IPAddress": "192.168.1.10",
        "HostName": "phone",
        "X_BT-COM_UserHostName": "My Phone",
        "Active": "1",
        "InterfaceType": "Wi-Fi",
        "Layer1Interface": "Device.WiFi.Radio.2.Interface",
        "BytesSent": "1024",
        "BytesReceived": "2048",
    }
    host = _params_to_host(params)
    assert host == Host(
        mac_address="AA:BB:CC:DD:EE:FF",
        ip_address="192.168.1.10",
        hostname="phone",
        user_friendly_name="My Phone",
        active=True,
        interface_type="Wi-Fi",
        frequency_band="5GHz",
        bytes_sent=1024,
        bytes_received=2048,
    )


def test_params_to_host_minimal():
    host = _params_to_host({"PhysAddress": "AA:BB:CC:DD:EE:FF"})
    assert host is not None
    assert host.mac_address == "AA:BB:CC:DD:EE:FF"
    assert host.ip_address == ""
    assert host.active is False
    assert host.frequency_band is None
    assert host.bytes_sent == 0


def test_params_to_host_missing_mac():
    assert _params_to_host({"IPAddress": "192.168.1.1"}) is None


def test_params_to_host_empty_mac():
    assert _params_to_host({"PhysAddress": ""}) is None


def test_params_to_host_inactive():
    host = _params_to_host({"PhysAddress": "AA:BB:CC:DD:EE:FF", "Active": "0"})
    assert host is not None
    assert host.active is False


# --- build_get_request ---


def test_build_get_request_round_trips():
    data = build_get_request(
        to_id="os::012345-SERIAL",
        from_id="usp-gui-admin",
        path="Device.Hosts.Host.",
    )
    record = Record().parse(data)
    assert record.to_id == "os::012345-SERIAL"
    assert record.from_id == "usp-gui-admin"
    assert record.no_session_context is not None

    msg = Msg().parse(record.no_session_context.payload)
    assert msg.header is not None
    assert msg.header.msg_type == HeaderMsgType.GET
    assert msg.body is not None
    assert msg.body.request is not None
    assert msg.body.request.get is not None
    assert msg.body.request.get.param_paths == ["Device.Hosts.Host."]


# --- parse_get_response ---


def test_parse_single_host():
    data = _build_response_bytes([
        GetRespRequestedPathResult(
            requested_path="Device.Hosts.Host.",
            err_code=0,
            resolved_path_results=[
                _host_path_result(1, {
                    "PhysAddress": "AA:BB:CC:DD:EE:FF",
                    "IPAddress": "192.168.1.10",
                    "HostName": "phone",
                    "Active": "1",
                }),
            ],
        ),
    ])
    hosts = parse_get_response(data)
    assert len(hosts) == 1
    assert hosts[0].mac_address == "AA:BB:CC:DD:EE:FF"
    assert hosts[0].ip_address == "192.168.1.10"
    assert hosts[0].active is True


def test_parse_multiple_hosts():
    data = _build_response_bytes([
        GetRespRequestedPathResult(
            requested_path="Device.Hosts.Host.",
            err_code=0,
            resolved_path_results=[
                _host_path_result(1, {
                    "PhysAddress": "AA:BB:CC:DD:EE:01",
                    "HostName": "phone",
                }),
                _host_path_result(2, {
                    "PhysAddress": "AA:BB:CC:DD:EE:02",
                    "HostName": "laptop",
                }),
            ],
        ),
    ])
    hosts = parse_get_response(data)
    assert len(hosts) == 2
    macs = {h.mac_address for h in hosts}
    assert macs == {"AA:BB:CC:DD:EE:01", "AA:BB:CC:DD:EE:02"}


def test_parse_sub_paths_merged():
    """WANStats sub-paths should merge into the parent host."""
    data = _build_response_bytes([
        GetRespRequestedPathResult(
            requested_path="Device.Hosts.Host.",
            err_code=0,
            resolved_path_results=[
                _host_path_result(1, {
                    "PhysAddress": "AA:BB:CC:DD:EE:FF",
                    "IPAddress": "192.168.1.10",
                }),
                _host_path_result(1, {
                    "BytesSent": "500",
                    "BytesReceived": "1000",
                }, sub_path="WANStats."),
            ],
        ),
    ])
    hosts = parse_get_response(data)
    assert len(hosts) == 1
    assert hosts[0].bytes_sent == 500
    assert hosts[0].bytes_received == 1000


def test_parse_host_without_mac_skipped():
    data = _build_response_bytes([
        GetRespRequestedPathResult(
            requested_path="Device.Hosts.Host.",
            err_code=0,
            resolved_path_results=[
                _host_path_result(1, {"IPAddress": "192.168.1.10"}),
                _host_path_result(2, {
                    "PhysAddress": "AA:BB:CC:DD:EE:FF",
                }),
            ],
        ),
    ])
    hosts = parse_get_response(data)
    assert len(hosts) == 1
    assert hosts[0].mac_address == "AA:BB:CC:DD:EE:FF"


def test_parse_empty_response():
    data = _build_response_bytes([
        GetRespRequestedPathResult(
            requested_path="Device.Hosts.Host.",
            err_code=0,
            resolved_path_results=[],
        ),
    ])
    hosts = parse_get_response(data)
    assert hosts == []


def test_parse_usp_body_error():
    body = Body(error=Error(err_code=7012, err_msg="Invalid path"))
    header = Header(msg_id="test-1", msg_type=HeaderMsgType.ERROR)
    msg = Msg(header=header, body=body)
    record = Record(
        version="1.4",
        to_id="controller",
        from_id="agent",
        payload_security=RecordPayloadSecurity.PLAINTEXT,
        no_session_context=NoSessionContextRecord(payload=bytes(msg)),
    )
    with pytest.raises(ProtocolError, match="USP error 7012"):
        parse_get_response(bytes(record))


def test_parse_path_result_error():
    data = _build_response_bytes([
        GetRespRequestedPathResult(
            requested_path="Device.Hosts.Host.",
            err_code=7012,
            err_msg="Invalid path",
            resolved_path_results=[],
        ),
    ])
    with pytest.raises(ProtocolError, match="USP error 7012"):
        parse_get_response(data)


def test_parse_missing_no_session_context():
    record = Record(
        version="1.4",
        to_id="controller",
        from_id="agent",
        payload_security=RecordPayloadSecurity.PLAINTEXT,
    )
    with pytest.raises(ProtocolError, match="missing no_session_context"):
        parse_get_response(bytes(record))


def test_parse_missing_get_resp():
    """Response with body but no get_resp should raise ProtocolError."""
    body = Body(response=Response())
    header = Header(msg_id="test-1", msg_type=HeaderMsgType.GET_RESP)
    msg = Msg(header=header, body=body)
    record = Record(
        version="1.4",
        to_id="controller",
        from_id="agent",
        payload_security=RecordPayloadSecurity.PLAINTEXT,
        no_session_context=NoSessionContextRecord(payload=bytes(msg)),
    )
    with pytest.raises(ProtocolError, match="missing expected get_resp"):
        parse_get_response(bytes(record))
