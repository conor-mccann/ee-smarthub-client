from dataclasses import dataclass


@dataclass
class Host:
    mac_address: str
    name: str = ""
    ip_address: str = ""
