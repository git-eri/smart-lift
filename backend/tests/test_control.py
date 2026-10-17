import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from app.managers.lift_manager import LiftManager
from app.models.messages import HelloMsg, LiftMovedMsg, MoveLiftMsg, StopStateMsg
from app.utils.message_parser import parse_msg


class Clock:
    now = 100.0

    def __call__(self):
        return self.now


class FakeConnections:
    def __init__(self):
        self.sent = []
        self.failed = set()

    async def send(self, peer, raw):
        self.sent.append((peer, json.loads(raw)))
        return peer not in self.failed

    async def broadcast_clients(self, raw):
        self.sent.append(("clients", json.loads(raw)))

    def messages(self, case, peer=None):
        return [msg for recipient, msg in self.sent if msg["case"] == case and (peer is None or recipient == peer)]


class ControlTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.clock = Clock()
        self.connections = FakeConnections()
        self.manager = LiftManager(self.connections, clock=self.clock,
                                   lift_info_path=Path(self.temp.name) / "names.json")
        await self.register("con1", [0, 1])
        await self.reset()
        self.connections.sent.clear()

    async def register(self, peer, lifts, stopped=True):
        await self.manager.recv_hello(peer, HelloMsg(
            case="hello", protocol_version=2, lifts=lifts,
            stop_latched=stopped, power_state=1,
        ))

    async def reset(self):
        await self.manager.reset_stop("cli1")
        for peer, reset_id in list(self.manager._reset_waiting.items()):
            await self.manager.recv_stop_state(peer, StopStateMsg(
                case="stop_state", stopped=False, reset_id=reset_id,
            ))

    def move(self, *, client="cli1", con="con1", lift=0, direction=0,
             command="press1", toggle=1, renew=False, epoch=None):
        return MoveLiftMsg(case="move_lift", client_id=client, con_id=con,
                           lift_id=lift, direction=direction, toggle=toggle,
                           command_id=command, renew=renew,
                           control_epoch=epoch or self.manager.control_epoch)

    async def test_boot_requires_acknowledged_reset(self):
        await self.manager.e_stop()
        await self.manager.send_move_lift(self.move())
        self.assertFalse(self.manager.active_lifts)
        await self.manager.reset_stop("cli1")
        self.assertTrue(self.manager.stopped)
        self.assertTrue(self.manager._reset_waiting)
        await self.reset()
        self.assertFalse(self.manager.stopped)

    async def test_opposite_direction_and_other_owner_are_rejected(self):
        await self.manager.send_move_lift(self.move())
        await self.manager.send_move_lift(self.move(client="cli2", command="press2", direction=1))
        await self.manager.send_move_lift(self.move(command="press3", direction=2))
        self.assertEqual(self.manager.active_lifts[("con1", 0)].command_id, "press1")
        self.assertEqual(len(self.connections.messages("move_lift", "con1")), 1)
        self.assertEqual(len(self.connections.messages("error")), 2)

    async def test_one_operator_can_hold_several_lifts_and_release_exactly_one(self):
        await self.manager.send_move_lift(self.move())
        await self.manager.send_move_lift(self.move(lift=1, command="press2"))
        await self.manager.send_move_lift(self.move(toggle=0))
        self.assertEqual(set(self.manager.active_lifts), {("con1", 1)})
        await self.manager.client_disconnected("cli1")
        self.assertFalse(self.manager.active_lifts)
        self.assertTrue(self.manager.stopped)

    async def test_foreign_release_and_old_release_do_not_cancel_new_press(self):
        await self.manager.send_move_lift(self.move())
        await self.manager.send_move_lift(self.move(client="cli2", toggle=0))
        self.assertIn(("con1", 0), self.manager.active_lifts)
        await self.manager.send_move_lift(self.move(toggle=0))
        await self.manager.send_move_lift(self.move(command="press2"))
        await self.manager.send_move_lift(self.move(toggle=0))
        self.assertEqual(self.manager.active_lifts[("con1", 0)].command_id, "press2")

    async def test_renewal_extends_hold_but_expired_renewal_cannot_restart_it(self):
        await self.manager.send_move_lift(self.move())
        self.clock.now += 0.3
        await self.manager.send_move_lift(self.move(renew=True))
        self.clock.now += 0.3
        await self.manager.expire_movements()
        self.assertIn(("con1", 0), self.manager.active_lifts)
        self.clock.now += 0.3
        await self.manager.expire_movements()
        self.assertFalse(self.manager.active_lifts)
        await self.manager.send_move_lift(self.move(renew=True))
        await self.manager.send_move_lift(self.move())
        self.assertFalse(self.manager.active_lifts)
        self.assertEqual(self.connections.messages("move_lift", "con1")[-1]["toggle"], 0)

    async def test_expiry_is_checked_before_renewal_even_without_watchdog_tick(self):
        await self.manager.send_move_lift(self.move())
        self.clock.now += 0.6
        await self.manager.send_move_lift(self.move(renew=True))
        self.assertFalse(self.manager.active_lifts)

    async def test_old_epoch_cannot_start_after_stop_and_reset(self):
        epoch = self.manager.control_epoch
        await self.manager.send_move_lift(self.move())
        await self.manager.e_stop()
        await self.reset()
        await self.manager.send_move_lift(self.move(command="queued", epoch=epoch))
        await self.manager.send_move_lift(self.move(renew=True))
        self.assertFalse(self.manager.active_lifts)
        await self.manager.send_move_lift(self.move(command="fresh"))
        self.assertIn(("con1", 0), self.manager.active_lifts)

    async def test_reset_waits_for_every_controller_and_old_ack_is_ignored(self):
        await self.register("con2", [2])
        await self.manager.reset_stop("cli1")
        pending = dict(self.manager._reset_waiting)
        await self.manager.recv_stop_state("con1", StopStateMsg(case="stop_state", stopped=False, reset_id="old"))
        self.assertEqual(self.manager._reset_waiting, pending)
        await self.manager.recv_stop_state("con1", StopStateMsg(case="stop_state", stopped=False, reset_id=pending["con1"]))
        self.assertTrue(self.manager.stopped)
        await self.manager.recv_stop_state("con2", StopStateMsg(case="stop_state", stopped=False, reset_id=pending["con2"]))
        self.assertFalse(self.manager.stopped)

    async def test_stop_during_reset_invalidates_pending_ack(self):
        await self.manager.e_stop()
        await self.manager.reset_stop("cli1")
        reset_id = self.manager._reset_waiting["con1"]
        await self.manager.e_stop()
        await self.manager.recv_stop_state("con1", StopStateMsg(case="stop_state", stopped=False, reset_id=reset_id))
        self.assertTrue(self.manager.stopped)
        self.assertTrue(self.manager.controllers["con1"]["stopped"])

    async def test_missing_reset_ack_keeps_stop_active(self):
        await self.manager.e_stop()
        await self.manager.reset_stop("cli1")
        self.clock.now += 3.1
        await self.manager.expire_movements()
        self.assertTrue(self.manager.stopped)
        self.assertFalse(self.manager._reset_waiting)

    async def test_disconnect_during_reset_cannot_silently_complete_reset(self):
        await self.register("con2", [2])
        await self.manager.reset_stop("cli1")
        await self.manager.controller_disconnected("con2")
        self.assertTrue(self.manager.stopped)
        self.assertFalse(self.manager._reset_waiting)

    async def test_expired_reset_ack_is_rejected_before_next_watchdog_tick(self):
        await self.manager.e_stop()
        await self.manager.reset_stop("cli1")
        reset_id = self.manager._reset_waiting["con1"]
        self.clock.now += 3.1
        await self.manager.recv_stop_state("con1", StopStateMsg(
            case="stop_state", stopped=False, reset_id=reset_id,
        ))
        self.assertTrue(self.manager.stopped)
        self.assertFalse(self.manager._reset_waiting)

    async def test_unknown_lift_is_not_forwarded(self):
        await self.manager.send_move_lift(self.move(lift=99))
        self.assertFalse(self.connections.messages("move_lift", "con1"))

    async def test_failed_send_does_not_leave_phantom_ownership(self):
        self.connections.failed.add("con1")
        await self.manager.send_move_lift(self.move())
        self.assertFalse(self.manager.active_lifts)
        self.assertFalse(self.manager.controllers["con1"]["ready"])

    async def test_controller_disconnect_clears_all_affected_holds(self):
        await self.manager.send_move_lift(self.move())
        await self.manager.send_move_lift(self.move(lift=1, command="press2"))
        await self.manager.controller_disconnected("con1")
        self.assertFalse(self.manager.active_lifts)
        self.assertNotIn("con1", self.manager.online_lifts)
        self.assertTrue(self.manager.stopped)

    async def test_idle_controller_reconnect_cannot_accept_pre_outage_start(self):
        old_epoch = self.manager.control_epoch
        await self.manager.controller_disconnected("con1")
        await self.register("con1", [0, 1], stopped=False)
        self.assertTrue(self.manager.stopped)
        await self.reset()
        await self.manager.send_move_lift(self.move(command="queuedBeforeOutage", epoch=old_epoch))
        self.assertFalse(self.manager.active_lifts)
        await self.manager.send_move_lift(self.move(command="afterReset"))
        self.assertIn(("con1", 0), self.manager.active_lifts)

    async def test_controller_cannot_spoof_ack_controller_id(self):
        await self.manager.send_move_lift(self.move())
        await self.manager.recv_lift_moved("con1", LiftMovedMsg(
            case="lift_moved", con_id="conSpoof", lift_id=0,
            direction=0, toggle=1, command_id="press1",
        ))
        self.assertEqual(self.connections.messages("lift_moved")[-1]["con_id"], "con1")

    async def test_concurrent_starts_have_one_owner(self):
        await asyncio.gather(*(self.manager.send_move_lift(self.move(
            client=f"cli{i}", command=f"press{i}", direction=i % 3,
        )) for i in range(20)))
        self.assertEqual(len(self.manager.active_lifts), 1)
        self.assertEqual(len(self.connections.messages("move_lift", "con1")), 1)

    async def test_name_write_is_persistent_and_failed_write_does_not_publish(self):
        await self.manager.change_name(0, "  Garage  ")
        stored = json.loads(self.manager._lift_info_path.read_text(encoding="utf8"))
        self.assertEqual(stored["0"]["name"], "Garage")
        def fail(*args):
            raise OSError("disk full")
        self.manager._atomic_write_json = fail
        with self.assertRaises(OSError):
            await self.manager.change_name(0, "Lost")
        self.assertEqual(self.manager.online_lifts["con1"][0]["name"], "Garage")


class MessageValidationTests(unittest.TestCase):
    def command(self):
        return dict(case="move_lift", con_id="con1", lift_id=0,
                    direction=0, toggle=1, command_id="press", control_epoch="epoch", renew=False)

    def test_missing_null_coerced_and_out_of_range_direction_are_rejected(self):
        for value in [None, True, "0", 0.0, -1, 3]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_msg(json.dumps({**self.command(), "direction": value}))
        missing = self.command()
        del missing["direction"]
        with self.assertRaises(ValueError):
            parse_msg(json.dumps(missing))

    def test_toggle_and_lift_id_cannot_be_coerced(self):
        for field, value in [("toggle", True), ("toggle", "1"), ("lift_id", 1.0), ("renew", "false")]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse_msg(json.dumps({**self.command(), field: value}))

    def test_legacy_or_oversized_messages_are_rejected(self):
        for raw in ['{"case":"hello","lifts":[0]}', '[]', '{', '{"case":"unknown"}', 'x' * 4097]:
            with self.subTest(raw=raw[:50]), self.assertRaises(ValueError):
                parse_msg(raw)


if __name__ == "__main__":
    unittest.main()
