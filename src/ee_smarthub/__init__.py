from importlib.metadata import version

from .client import SmartHubClient
from .exceptions import (
    AuthenticationError,
    CommunicationError,
    ProtocolError,
    SmartHubError,
)
from .models import Host

__version__ = version("ee-smarthub")

__all__ = [
    "AuthenticationError",
    "CommunicationError",
    "Host",
    "ProtocolError",
    "SmartHubClient",
    "SmartHubError",
    "__version__",
]
