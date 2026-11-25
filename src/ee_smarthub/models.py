from dataclasses import dataclass


@dataclass
class Host:
    """A device connected to the SmartHub."""

    mac_address: str
    ip_address: str = ""
    hostname: str = ""
    user_friendly_name: str = ""
    interface_type: str = ""
    active: bool = False
    frequency_band: str | None = None
    bytes_sent: int = 0
    bytes_received: int = 0
    # False when the router reports a blank AssociatedDevice and Layer1Interface,
    # seen on a departed phone that was still marked active.
    connected: bool = True

    @property
    def name(self) -> str:
        """Return the best available name for the device."""
        return self.user_friendly_name or self.hostname or self.mac_address
