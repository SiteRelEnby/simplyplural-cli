"""
Protocol definitions for daemon communication

This module defines the protocol used for communication between the daemon
and CLI clients over Unix domain sockets, as well as constants for the
WebSocket protocol with Simply Plural's API.
"""

from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass
import json
import uuid


# Protocol version
PROTOCOL_VERSION = 1


class CommandType(str, Enum):
    """Available commands for daemon communication"""
    PING = "ping"
    STATUS = "status"
    FRONTING = "fronting"
    MEMBERS = "members"
    CUSTOM_FRONTS = "custom-fronts"
    SWITCH = "switch"
    RELOAD = "reload"


class ResponseStatus(str, Enum):
    """Response status codes"""
    OK = "ok"
    ERROR = "error"


class WebSocketOp(str, Enum):
    """WebSocket operation types for Simply Plural API"""
    AUTHENTICATE = "authenticate"
    PING = "ping"


class WSMessageType(str, Enum):
    """WebSocket message types from Simply Plural API"""
    UPDATE = "update"


class WSTarget(str, Enum):
    """WebSocket update target collections"""
    FRONT_HISTORY = "frontHistory"
    MEMBERS = "members"
    CUSTOM_FRONTS = "customFronts"
    BOARD_MESSAGES = "boardMessages"
    # Add more as we discover them


class WSOperationType(str, Enum):
    """WebSocket operation types in update messages"""
    INSERT = "insert"
    UPDATE = "update"
    DELETE = "delete"


@dataclass
class Request:
    """Request from client to daemon"""
    command: CommandType
    version: int = PROTOCOL_VERSION
    args: Dict[str, Any] = None
    request_id: str = None
    
    def __post_init__(self):
        """Initialize default values"""
        if self.args is None:
            self.args = {}
        if self.request_id is None:
            self.request_id = str(uuid.uuid4())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Request':
        """Create Request from dictionary"""
        return cls(
            version=data.get('version', PROTOCOL_VERSION),
            command=CommandType(data['command']),
            args=data.get('args', {}),
            request_id=data.get('request_id', str(uuid.uuid4()))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Request to dictionary"""
        return {
            'version': self.version,
            'command': self.command.value,
            'args': self.args,
            'request_id': self.request_id
        }
    
    def to_json(self) -> str:
        """Serialize to JSON"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def create(cls, command: CommandType, args: Optional[Dict[str, Any]] = None) -> 'Request':
        """Create a new request with auto-generated ID"""
        return cls(
            command=command,
            version=PROTOCOL_VERSION,
            args=args,
            request_id=str(uuid.uuid4())
        )


@dataclass
class Response:
    """Response from daemon to client"""
    status: ResponseStatus
    request_id: str
    version: int = PROTOCOL_VERSION
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Response':
        """Create Response from dictionary"""
        return cls(
            version=data.get('version', PROTOCOL_VERSION),
            status=ResponseStatus(data['status']),
            data=data.get('data'),
            error=data.get('error'),
            request_id=data.get('request_id', '')
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Response to dictionary"""
        return {
            'version': self.version,
            'status': self.status.value,
            'data': self.data,
            'error': self.error,
            'request_id': self.request_id
        }
    
    def to_json(self) -> str:
        """Serialize to JSON"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def success(cls, request_id: str, data: Optional[Dict[str, Any]] = None) -> 'Response':
        """Create a successful response"""
        return cls(
            status=ResponseStatus.OK,
            request_id=request_id,
            version=PROTOCOL_VERSION,
            data=data,
            error=None
        )
    
    @classmethod
    def error(cls, request_id: str, error_message: str) -> 'Response':
        """Create an error response"""
        return cls(
            status=ResponseStatus.ERROR,
            request_id=request_id,
            version=PROTOCOL_VERSION,
            data=None,
            error=error_message
        )


@dataclass
class WSUpdateMessage:
    """Parsed WebSocket update message from Simply Plural API"""
    msg_type: str  # Should be "update"
    target: str    # Collection name (frontHistory, members, etc.)
    results: list  # List of update operations
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WSUpdateMessage':
        """Create from WebSocket message dictionary"""
        return cls(
            msg_type=data.get('msg', ''),
            target=data.get('target', ''),
            results=data.get('results', [])
        )
    
    def is_update_message(self) -> bool:
        """Check if this is a valid update message (case-insensitive)"""
        return self.msg_type.lower() == WSMessageType.UPDATE.value.lower()


@dataclass
class WSUpdateResult:
    """Single update result from WebSocket message"""
    operation_type: str  # insert, update, delete
    object_id: str       # ID of the object
    content: Dict[str, Any]  # The actual object data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'WSUpdateResult':
        """Create from result dictionary"""
        return cls(
            operation_type=data.get('operationType', ''),
            object_id=data.get('id', ''),
            content=data.get('content', {})
        )


# WebSocket keepalive constants
WS_KEEPALIVE_INTERVAL = 10  # seconds
WS_KEEPALIVE_MESSAGE = "ping"

# WebSocket reconnection constants
WS_RECONNECT_INITIAL_DELAY = 1  # seconds
WS_RECONNECT_MAX_DELAY = 60     # seconds
WS_RECONNECT_MULTIPLIER = 2     # exponential backoff multiplier

# Simply Plural WebSocket endpoints
WS_ENDPOINT_PROD = "wss://api.apparyllis.com/v1/socket"
WS_ENDPOINT_DEV = "wss://devapi.apparyllis.com/v1/socket"
