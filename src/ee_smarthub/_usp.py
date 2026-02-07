import re
import uuid

from .exceptions import ProtocolError
from .models import Host
from .proto.usp import Body, Get, Header, HeaderMsgType, Msg, Request
from .proto.usp_record import NoSessionContextRecord, Record, RecordPayloadSecurity

_HOST_PATH_RE = re.compile(r"^(Device\.Hosts\.Host\.\d+\.)")

_FREQUENCY_BANDS = {"Radio.1": "2.4GHz", "Radio.2": "5GHz", "Radio.3": "6GHz"}


def build_get_request(to_id: str, from_id: str, path: str) -> bytes:
    """Build a Record-framed USP Get request for the given path."""
    get = Get(param_paths=[path], max_depth=0)
    request = Request(get=get)
    body = Body(request=request)
    msg_id = str(uuid.uuid4())
    header = Header(msg_id=msg_id, msg_type=HeaderMsgType.GET)
    msg = Msg(header=header, body=body)
    msg_bytes = bytes(msg)
    no_session_context = NoSessionContextRecord(payload=msg_bytes)
    record = Record(
        version="1.4",
        to_id=to_id,
        from_id=from_id,
        payload_security=RecordPayloadSecurity.PLAINTEXT,
        no_session_context=no_session_context,
    )
    return bytes(record)


def parse_get_response(data: bytes) -> list[Host]:
    """Parse a USP GetResponse Record into Host objects.

    Raises ProtocolError on USP errors or malformed responses.
    """
    record = Record().parse(data)

    if record.no_session_context is None:
        raise ProtocolError("Record missing no_session_context")

    msg_bytes = record.no_session_context.payload
    msg = Msg().parse(msg_bytes)

    if msg.body is not None and msg.body.error is not None:
        err = msg.body.error
        raise ProtocolError(f"USP error {err.err_code}: {err.err_msg}")

    if msg.body is None or msg.body.response is None or msg.body.response.get_resp is None:
        raise ProtocolError("Response missing expected get_resp structure")

    get_resp = msg.body.response.get_resp
    for req_path_result in get_resp.req_path_results:
        if req_path_result.err_code != 0:
            raise ProtocolError(
                f"USP error {req_path_result.err_code}: {req_path_result.err_msg}"
            )

    # Group resolved paths by host (e.g. Device.Hosts.Host.1.)
    # so sub-paths like WANStats get merged into the parent host.
    grouped: dict[str, dict[str, str]] = {}
    for req_path_result in get_resp.req_path_results:
        for resolved in req_path_result.resolved_path_results:
            match = _HOST_PATH_RE.match(resolved.resolved_path)
            if not match:
                continue
            host_prefix = match.group(1)
            params = grouped.setdefault(host_prefix, {})
            params.update(resolved.result_params)

    return [host for g in grouped.values() if (host := _params_to_host(g)) is not None]


def _safe_int(value: str) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return 0


def _extract_frequency(layer1_interface: str) -> str | None:
    for key, band in _FREQUENCY_BANDS.items():
        if key in layer1_interface:
            return band
    return None


def _params_to_host(params: dict[str, str]) -> Host | None:
    mac = params.get("PhysAddress")
    if not mac:
        return None

    return Host(
        mac_address=mac,
        ip_address=params.get("IPAddress", ""),
        hostname=params.get("HostName", ""),
        user_friendly_name=params.get("X_BT-COM_UserHostName", ""),
        active=params.get("Active", "0") == "1",
        interface_type=params.get("InterfaceType", ""),
        frequency_band=_extract_frequency(params.get("Layer1Interface", "")),
        bytes_sent=_safe_int(params.get("BytesSent", "")),
        bytes_received=_safe_int(params.get("BytesReceived", "")),
    )
