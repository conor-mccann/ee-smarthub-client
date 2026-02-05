import uuid

from .exceptions import ProtocolError
from .models import Host
from .proto.usp import Body, Get, Header, HeaderMsgType, Msg, Request
from .proto.usp_record import NoSessionContextRecord, Record, RecordPayloadSecurity

_HOST_FIELD_MAP = {
    "HostName": "name",
    "IPAddress": "ip_address",
    "MACAddress": "mac_address",
}


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
    hosts: list[Host] = []
    for req_path_result in get_resp.req_path_results:
        if req_path_result.err_code != 0:
            raise ProtocolError(
                f"USP error {req_path_result.err_code}: {req_path_result.err_msg}"
            )
        for resolved in req_path_result.resolved_path_results:
            host = _params_to_host(resolved.result_params)
            if host is not None:
                hosts.append(host)

    return hosts


def _params_to_host(result_params: dict[str, str]) -> Host | None:
    mapped: dict[str, str] = {}
    for key, value in result_params.items():
        leaf = key.rsplit(".", 1)[-1]
        if leaf in _HOST_FIELD_MAP:
            mapped[_HOST_FIELD_MAP[leaf]] = value

    if "mac_address" not in mapped:
        return None

    return Host(
        mac_address=mapped["mac_address"],
        name=mapped.get("name", ""),
        ip_address=mapped.get("ip_address", ""),
    )
