"""Shared wire limits; changing the protocol version requires coordinated peers."""

PROTOCOL_VERSION = 2
MAX_MESSAGE_BYTES = 4096
MAX_PEER_CONNECTIONS = 128
MAX_LIFT_ID = 1_000_000
IDENTIFIER_PATTERN = r"^[A-Za-z0-9_-]+$"
CONTROLLER_ID_PATTERN = r"^con[A-Za-z0-9_-]{1,61}$"
PEER_ID_PATTERN = r"^(?:con|cli)[A-Za-z0-9_-]{1,61}$"
