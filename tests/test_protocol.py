"""Tests for daemon protocol serialization and data classes"""

import json
from simplyplural.daemon_protocol import (
    Request,
    Response,
    CommandType,
    ResponseStatus,
    WSUpdateMessage,
    WSUpdateResult,
    PROTOCOL_VERSION,
    WS_KEEPALIVE_INTERVAL,
    WS_KEEPALIVE_MESSAGE,
)


class TestRequest:
    def test_create_generates_uuid(self):
        req = Request.create(CommandType.PING)
        assert req.request_id is not None
        assert len(req.request_id) == 36  # UUID format

    def test_create_with_args(self):
        req = Request.create(CommandType.SWITCH, args={"entities": ["Alice"]})
        assert req.args == {"entities": ["Alice"]}
        assert req.command == CommandType.SWITCH

    def test_round_trip_serialization(self):
        original = Request.create(CommandType.FRONTING)
        json_str = original.to_json()
        restored = Request.from_dict(json.loads(json_str))
        assert restored.command == original.command
        assert restored.request_id == original.request_id
        assert restored.version == PROTOCOL_VERSION

    def test_default_args_is_empty_dict(self):
        req = Request.create(CommandType.PING)
        assert req.args == {}


class TestResponse:
    def test_success_response(self):
        resp = Response.success("req-123", {"pong": True})
        assert resp.status == ResponseStatus.OK
        assert resp.data == {"pong": True}
        assert resp.error is None

    def test_error_response(self):
        resp = Response.error("req-123", "something broke")
        assert resp.status == ResponseStatus.ERROR
        assert resp.error == "something broke"
        assert resp.data is None

    def test_round_trip_serialization(self):
        original = Response.success("req-456", {"count": 5})
        json_str = original.to_json()
        restored = Response.from_dict(json.loads(json_str))
        assert restored.status == ResponseStatus.OK
        assert restored.data == {"count": 5}
        assert restored.request_id == "req-456"


class TestWSUpdateMessage:
    def test_parse_update_message(self):
        data = {
            "msg": "update",
            "target": "frontHistory",
            "results": [{"operationType": "insert", "id": "abc", "content": {}}],
        }
        msg = WSUpdateMessage.from_dict(data)
        assert msg.is_update_message()
        assert msg.target == "frontHistory"
        assert len(msg.results) == 1

    def test_non_update_message(self):
        msg = WSUpdateMessage.from_dict({"msg": "authenticated", "target": "", "results": []})
        assert not msg.is_update_message()

    def test_case_insensitive_update_check(self):
        msg = WSUpdateMessage.from_dict({"msg": "Update", "target": "members", "results": []})
        assert msg.is_update_message()


class TestWSUpdateResult:
    def test_parse_result(self):
        data = {
            "operationType": "insert",
            "id": "front999",
            "content": {"member": "m1", "live": True},
        }
        result = WSUpdateResult.from_dict(data)
        assert result.operation_type == "insert"
        assert result.object_id == "front999"
        assert result.content["live"] is True

    def test_missing_fields_default(self):
        result = WSUpdateResult.from_dict({})
        assert result.operation_type == ""
        assert result.object_id == ""
        assert result.content == {}


class TestConstants:
    def test_keepalive_interval(self):
        assert WS_KEEPALIVE_INTERVAL == 10

    def test_keepalive_message_is_ping(self):
        assert WS_KEEPALIVE_MESSAGE == "ping"
