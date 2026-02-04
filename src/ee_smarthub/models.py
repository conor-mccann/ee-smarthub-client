from dataclasses import dataclass


@dataclass
class Host:
    name: str
    ip_address: str
    mac_address: str
