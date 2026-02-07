class SmartHubError(Exception):
    """Base exception for all ee_smarthub errors."""


class CommunicationError(SmartHubError):
    """Failed to connect to or communicate with the router."""


class AuthenticationError(SmartHubError):
    """Router rejected the provided credentials."""


class ProtocolError(SmartHubError):
    """USP protocol-level error in the response."""
