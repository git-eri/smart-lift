import contextlib
import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.managers.connection_manager import ConnectionManager
from app.managers.lift_manager import LiftManager


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        directory = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.directory = Path(directory)
        self.cm = ConnectionManager()
        self.lm = LiftManager(self.cm, lift_info_path=self.directory / "names.json")
        main = importlib.import_module("app.main")
        for name in ["client_handler", "controller_handler", "client_routes", "controller_routes"]:
            importlib.import_module("app.websocket." + name)
        for name, module in list(sys.modules.items()):
            if name.startswith("app.") and module is not None:
                if hasattr(module, "lm"):
                    self.stack.enter_context(patch.object(module, "lm", self.lm))
                if hasattr(module, "cm"):
                    self.stack.enter_context(patch.object(module, "cm", self.cm))
        self.stack.enter_context(patch.dict(os.environ, {
            "SMARTLIFT_BIN_DIR": str(self.directory), "SMARTLIFT_CONTROLLER_TOKEN": "",
            "SMARTLIFT_ALLOWED_ORIGINS": "",
        }))
        self.client = self.stack.enter_context(TestClient(main.app))

    @staticmethod
    def receive_case(socket, case, predicate=lambda message: True):
        for _ in range(40):
            message = socket.receive_json()
            if message["case"] == case and predicate(message):
                return message
        raise AssertionError(f"Did not receive {case}")

    def test_websocket_handshake_reset_move_stop_and_duplicate_identity(self):
        with self.client.websocket_connect("/api/ws/cliTest", headers={"origin": "http://testserver"}) as operator:
            self.receive_case(operator, "control_state")
            with self.client.websocket_connect("/api/ws/conTest") as controller:
                controller.send_json({"case": "hello", "protocol_version": 2,
                                      "lifts": [0], "power_state": 1, "stop_latched": True})
                self.assertEqual(self.receive_case(controller, "controller_ready")["protocol_version"], 2)
                self.receive_case(controller, "stop")
                controller.send_json({"case": "stop_state", "stopped": True})
                self.receive_case(operator, "online_lifts", lambda msg: "conTest" in msg["lifts"])
                with self.assertRaises(WebSocketDisconnect):
                    with self.client.websocket_connect("/api/ws/conTest"):
                        pass
                operator.send_json({"case": "reset_stop"})
                reset = self.receive_case(controller, "reset_stop")
                controller.send_json({"case": "stop_state", "stopped": False, "reset_id": reset["reset_id"]})
                state = self.receive_case(operator, "control_state", lambda msg: not msg["stopped"])
                command = dict(case="move_lift", con_id="conTest", lift_id=0,
                               direction=0, toggle=1, command_id="integration",
                               control_epoch=state["control_epoch"], renew=False)
                operator.send_json(command)
                move = self.receive_case(controller, "move_lift")
                self.assertEqual(move["command_id"], "integration")
                controller.send_json({
                    "case": "lift_moved", "con_id": "conSpoof", "lift_id": 0,
                    "direction": 0, "toggle": 1, "command_id": "integration",
                })
                self.assertEqual(self.receive_case(operator, "lift_moved")["con_id"], "conTest")
                operator.send_json({"case": "stop"})
                self.receive_case(controller, "stop")
                self.receive_case(operator, "control_state", lambda msg: msg["stopped"])
                operator.send_json({**command, "renew": True})
                self.assertIn("STOP", self.receive_case(operator, "error")["detail"])

    def test_invalid_controller_handshake_is_closed_and_cleaned_up(self):
        with self.client.websocket_connect("/api/ws/conLegacy") as controller:
            controller.send_json({"case": "hello", "lifts": [0]})
            with self.assertRaises(WebSocketDisconnect):
                controller.receive_json()
        self.assertNotIn("conLegacy", self.lm.controllers)

    def test_foreign_browser_origin_is_rejected(self):
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/api/ws/cliForeign", headers={"origin": "https://unrelated.example"}):
                pass

    def test_arduino_default_origin_is_accepted_for_controller(self):
        with self.client.websocket_connect("/api/ws/conArduino", headers={"origin": "file://"},
                                           subprotocols=["arduino"]) as controller:
            controller.send_json({"case": "hello", "protocol_version": 2,
                                  "lifts": [0], "power_state": 1, "stop_latched": True})
            self.assertEqual(self.receive_case(controller, "controller_ready")["protocol_version"], 2)
            self.receive_case(controller, "stop")

    def test_arduino_origin_does_not_bypass_browser_origin_policy(self):
        for origin in ["file://", "file:///", "null", "http://[invalid"]:
            with self.subTest(origin=origin), self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect("/api/ws/cliFile", headers={"origin": origin}):
                    pass

    def test_foreign_http_origin_is_still_rejected_for_controller(self):
        with self.assertRaises(WebSocketDisconnect):
            with self.client.websocket_connect("/api/ws/conForeign", headers={"origin": "https://unrelated.example"}):
                pass

    def test_arduino_default_origin_does_not_bypass_controller_token(self):
        with patch.dict(os.environ, {"SMARTLIFT_CONTROLLER_TOKEN": "private-test-token"}):
            with self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect("/api/ws/conArduino", headers={"origin": "file://"}):
                    pass
            with self.client.websocket_connect("/api/ws/conArduino", headers={
                "origin": "file://", "x-controller-token": "private-test-token",
            }) as controller:
                controller.send_json({"case": "hello", "protocol_version": 2,
                                      "lifts": [0], "power_state": 1, "stop_latched": True})
                self.receive_case(controller, "controller_ready")

    def test_controller_token_is_required_when_configured(self):
        with patch.dict(os.environ, {"SMARTLIFT_CONTROLLER_TOKEN": "private-test-token"}):
            with self.assertRaises(WebSocketDisconnect):
                with self.client.websocket_connect("/api/ws/conWrong"):
                    pass
            response = self.client.get("/api/update/conTest")
            self.assertEqual(response.status_code, 403)
            self.assertEqual(self.client.get("/api/update/conTest", headers={"x-controller-token": "private-test-token"}).status_code, 304)

    def test_invalid_operator_message_does_not_become_a_movement(self):
        with self.client.websocket_connect("/api/ws/cliInvalid") as operator:
            self.receive_case(operator, "control_state")
            operator.send_json({"case": "move_lift", "lift_id": 0, "toggle": 1})
            self.receive_case(operator, "error")
            self.assertFalse(self.lm.active_lifts)

    def test_firmware_discovery_handles_specific_and_unrelated_filenames(self):
        (self.directory / "0.06.00.bin").write_bytes(b"generic")
        (self.directory / "conTest-0.06.00.bin").write_bytes(b"specific")
        (self.directory / "conOther-9.0.0.bin").write_bytes(b"wrong")
        (self.directory / "notes.bin").write_bytes(b"wrong")
        response = self.client.get("/api/update/conTest", headers={"x-esp8266-version": "0.05.02"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"specific")
        self.assertEqual(response.headers["content-type"], "application/octet-stream")
        self.assertEqual(self.client.get("/api/update/conTest", headers={"x-esp8266-version": "0.06.00"}).status_code, 304)
        self.assertEqual(self.client.get("/api/update/conTest", headers={"x-esp8266-version": "invalid"}).status_code, 400)

    def test_firmware_without_binary_returns_no_update(self):
        self.assertEqual(self.client.get("/api/update/conTest").status_code, 304)

    def test_health_flat_route_and_persistent_name(self):
        self.assertEqual(self.client.get("/api/health").json()["protocol_version"], 2)
        self.assertEqual(self.client.get("/api/lifts/online/flat").json(), [])
        result = self.client.post("/api/admin/lift-rename", json={"lift_id": 0, "new_name": "Garage"})
        self.assertEqual(result.status_code, 200)
        self.assertEqual(json.loads((self.directory / "names.json").read_text())["0"]["name"], "Garage")
        self.assertEqual(self.client.post("/api/admin/lift-rename", json={"lift_id": 0, "new_name": "  "}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
