"""Tests for the Launch plugin's runtime, against a fake app connection.

    /usr/bin/python3 -m unittest discover -s streamdeck/tests

Runs on the system Python, like the plugin itself.
"""

from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugins/com.jonathanleek.launch.sdPlugin"))

import launch  # noqa: E402
import render  # noqa: E402
from deck import Deck  # noqa: E402
from sources import SOURCES, Source, View  # noqa: E402


class FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, text: str) -> None:
        self.sent.append(json.loads(text))

    def events(self, name: str) -> list[dict]:
        return [m for m in self.sent if m["event"] == name]


class Counter(Source):
    """Shows a number; turning adds ticks, pressing resets, long tap doubles."""

    interval = 10.0

    def view(self, ctx):
        n = ctx.state.get("n", 0)
        return View(title=str(n), image=render.tile([str(n)]), feedback={"value": str(n)})

    def press(self, ctx):
        ctx.state["n"] = 0

    def rotate(self, ctx, ticks):
        ctx.state["n"] = ctx.state.get("n", 0) + ticks

    def tap(self, ctx, hold):
        if hold:
            ctx.state["n"] = ctx.state.get("n", 0) * 2


class Broken(Source):
    def view(self, ctx):
        raise RuntimeError("boom")


def svg(set_image: dict) -> str:
    """The SVG markup inside a setImage message."""
    return base64.b64decode(set_image["payload"]["image"].split(",", 1)[1]).decode()


def appear(context: str, action: str, settings: dict, controller: str = "Keypad") -> dict:
    return {
        "event": "willAppear", "action": action, "context": context, "device": "dev1",
        "payload": {"controller": controller, "settings": settings, "coordinates": {"column": 0, "row": 0}},
    }


class Base(unittest.TestCase):
    def setUp(self) -> None:
        SOURCES["counter"] = Counter()
        SOURCES["broken"] = Broken()
        self.addCleanup(SOURCES.pop, "counter")
        self.addCleanup(SOURCES.pop, "broken")
        self.ws = FakeWS()
        self.deck = Deck(self.ws, "plugin-ctx")

    def handle(self, msg: dict) -> None:
        launch.handle(self.deck, msg)

    def tap_key(self, settings: dict, seconds: float = 0.1, context: str = "k1") -> None:
        """Press and release a status key, holding it for `seconds`."""
        msg = {"action": launch.STATUS, "context": context, "payload": {"settings": settings}}
        with mock.patch.object(launch.time, "monotonic", return_value=100.0):
            self.handle({"event": "keyDown", **msg})
        with mock.patch.object(launch.time, "monotonic", return_value=100.0 + seconds):
            self.handle({"event": "keyUp", **msg})


class PluginTest(Base):

    def test_status_key_draws_on_appear(self):
        self.handle(appear("k1", launch.STATUS, {"source": "counter"}))
        (img,) = self.ws.events("setImage")
        self.assertEqual(img["context"], "k1")
        self.assertTrue(img["payload"]["image"].startswith("data:image/svg+xml;base64,"))
        self.assertNotIn("#", img["payload"]["image"])  # a raw '#' would end the URL
        self.assertTrue(svg(img).startswith("<svg"))
        self.assertEqual(self.ws.events("setTitle")[0]["payload"]["title"], "0")

    def test_only_changes_are_sent(self):
        self.handle(appear("k1", launch.STATUS, {"source": "counter"}))
        self.ws.sent.clear()
        self.deck.refresh(self.deck.get("k1"))
        self.assertEqual(self.ws.sent, [])

    def test_refresher_skips_keys_not_due_or_gone(self):
        self.handle(appear("k1", launch.STATUS, {"source": "counter"}))
        ctx = self.deck.get("k1")
        due = ctx.due
        ctx.state["n"] = 5
        self.ws.sent.clear()
        self.deck.refresh_due(due - 1)
        self.assertEqual(self.ws.sent, [])
        self.deck.refresh_due(due)
        self.assertEqual(self.ws.events("setTitle")[0]["payload"]["title"], "5")
        self.handle({"event": "willDisappear", "context": "k1", "payload": {}})
        ctx.state["n"] = 6
        self.ws.sent.clear()
        self.deck.refresh_due(due + 100)
        self.assertEqual(self.ws.sent, [])

    def test_dial_inputs_reach_source_and_redraw(self):
        self.handle(appear("d1", launch.DIAL, {"source": "counter"}, "Encoder"))
        self.handle({"event": "dialRotate", "action": launch.DIAL, "context": "d1", "payload": {"ticks": 3}})
        self.assertEqual(self.ws.events("setFeedback")[-1]["payload"], {"value": "3"})
        self.handle({"event": "touchTap", "action": launch.DIAL, "context": "d1", "payload": {"hold": True}})
        self.assertEqual(self.ws.events("setFeedback")[-1]["payload"], {"value": "6"})
        self.handle({"event": "dialDown", "action": launch.DIAL, "context": "d1", "payload": {"settings": {"source": "counter"}}})
        self.assertEqual(self.ws.events("setFeedback")[-1]["payload"], {"value": "0"})

    def test_state_survives_leaving_the_page(self):
        self.handle(appear("d1", launch.DIAL, {"source": "counter"}, "Encoder"))
        self.handle({"event": "dialRotate", "action": launch.DIAL, "context": "d1", "payload": {"ticks": 2}})
        self.handle({"event": "willDisappear", "context": "d1", "payload": {}})
        self.ws.sent.clear()
        self.handle(appear("d1", launch.DIAL, {"source": "counter"}, "Encoder"))
        self.assertEqual(self.ws.events("setFeedback")[-1]["payload"], {"value": "2"})

    def test_broken_source_shows_error_tile(self):
        with self.assertLogs("launch.deck", "ERROR"):
            self.handle(appear("k1", launch.STATUS, {"source": "broken"}))
        (img,) = self.ws.events("setImage")
        self.assertIn(">error<", svg(img))

    def test_switch_key(self):
        self.handle({"event": "keyDown", "action": launch.SWITCH, "context": "s1", "device": "dev1",
                     "payload": {"settings": {"profile": "Customers", "page": 3}}})
        self.handle({"event": "keyDown", "action": launch.SWITCH, "context": "s2", "device": "dev1",
                     "payload": {"settings": {"back": True}}})
        go, back = self.ws.events("switchToProfile")
        self.assertEqual(go, {"event": "switchToProfile", "context": "plugin-ctx", "device": "dev1",
                              "payload": {"profile": "Customers", "page": 3}})
        self.assertEqual(back["payload"], {})

    def test_bad_switch_settings_alert(self):
        with mock.patch.object(launch.log, "exception"):
            self.ws.recv = mock.Mock(side_effect=[
                json.dumps({"event": "keyDown", "action": launch.SWITCH, "context": "s1", "device": "dev1",
                            "payload": {"settings": {}}}),
                ConnectionError("closed"),
            ])
            with self.assertRaises(ConnectionError):
                launch.serve(self.deck)
        self.assertEqual(self.ws.events("showAlert")[0]["context"], "s1")

    def test_run_key_unchanged(self):
        with mock.patch.object(launch, "start") as start:
            self.handle({"event": "keyDown", "action": launch.RUN, "context": "r1",
                         "payload": {"settings": {"argv": ["/usr/bin/true"]}}})
        start.assert_called_once_with({"argv": ["/usr/bin/true"]})
        self.assertEqual(self.ws.events("showOk")[0]["context"], "r1")

    def test_status_key_with_argv_runs_it(self):
        settings = {"source": "counter", "argv": ["/usr/bin/true"]}
        self.handle(appear("k1", launch.STATUS, settings))
        self.deck.get("k1").state["n"] = 4
        with mock.patch.object(launch, "start") as start:
            self.tap_key(settings)
        start.assert_called_once()
        self.assertEqual(self.deck.get("k1").state["n"], 4)  # source press not called

    def test_status_key_press_goes_to_source(self):
        self.handle(appear("k1", launch.STATUS, {"source": "counter"}))
        self.deck.get("k1").state["n"] = 4
        self.tap_key({"source": "counter"})
        self.assertEqual(self.ws.events("setTitle")[-1]["payload"]["title"], "0")


class Holder(Counter):
    def hold(self, ctx):
        ctx.state["n"] = 99


class HoldTest(Base):
    def setUp(self) -> None:
        super().setUp()
        SOURCES["holder"] = Holder()
        self.addCleanup(SOURCES.pop, "holder")

    def test_short_press_is_press_long_is_hold(self):
        self.handle(appear("k1", launch.STATUS, {"source": "holder"}))
        self.deck.get("k1").state["n"] = 4
        self.tap_key({"source": "holder"}, 0.2)
        self.assertEqual(self.deck.get("k1").state["n"], 0)
        self.tap_key({"source": "holder"}, 1.5)
        self.assertEqual(self.deck.get("k1").state["n"], 99)

    def test_hold_without_hold_hook_runs_argv(self):
        settings = {"source": "counter", "argv": ["/usr/bin/true"]}
        self.handle(appear("k1", launch.STATUS, settings))
        with mock.patch.object(launch, "start") as start:
            self.tap_key(settings, 1.5)
        start.assert_called_once()

    def test_dial_press_runs_argv(self):
        settings = {"source": "counter", "argv": ["/usr/bin/open", "-a", "Activity Monitor"]}
        self.handle(appear("d1", launch.DIAL, settings, "Encoder"))
        with mock.patch.object(launch, "start") as start:
            self.handle({"event": "dialDown", "action": launch.DIAL, "context": "d1", "payload": {"settings": settings}})
        start.assert_called_once_with(settings)


class MacSourcesTest(Base):
    def setUp(self) -> None:
        super().setUp()
        for name, value in {
            "cpu_percent": 37.4, "gpu_percent": 12.0, "memory": (160.4, 256.0, 2),
            "top_processes": [("WindowServer", 43.0, 0.9), ("Plex", 18.2, 0.95)],
        }.items():
            p = mock.patch.object(launch.mac, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    def test_load_overview_then_turn_to_top_lists(self):
        self.handle(appear("d1", launch.DIAL, {"source": "load"}, "Encoder"))
        self.assertEqual(self.ws.events("setFeedbackLayout")[-1]["payload"], {"layout": "layouts/load.json"})
        fb = self.ws.events("setFeedback")[-1]["payload"]
        self.assertEqual((fb["cpu_val"], fb["gpu_val"], fb["mem_val"]), ("37%", "12%", "160G"))
        self.assertEqual(fb["mem_bar"], {"value": 63, "bar_fill_c": launch.mac.C_MEM[2]})

        self.handle({"event": "dialRotate", "action": launch.DIAL, "context": "d1", "payload": {"ticks": 1}})
        self.assertEqual(self.ws.events("setFeedbackLayout")[-1]["payload"], {"layout": "layouts/top.json"})
        fb = self.ws.events("setFeedback")[-1]["payload"]
        self.assertEqual((fb["head"], fb["name0"], fb["val0"], fb["name2"], fb["val2"]),
                         ("Top CPU", "WindowServer", "43%", "", ""))

        self.handle({"event": "dialRotate", "action": launch.DIAL, "context": "d1", "payload": {"ticks": 1}})
        self.assertEqual(self.ws.events("setFeedback")[-1]["payload"]["val1"], "0.9G")
        self.handle({"event": "dialRotate", "action": launch.DIAL, "context": "d1", "payload": {"ticks": 1}})
        self.assertEqual(self.ws.events("setFeedbackLayout")[-1]["payload"], {"layout": "layouts/load.json"})

    def test_containers_states(self):
        cases = [
            (None, ">off<"),
            ([], ">0<"),
            (["example-project_f98708"] * 6, ">example-project<"),
            (["a", "b"], ">2 projects<"),
        ]
        for running, expect in cases:
            with self.subTest(running=running), mock.patch.object(launch.mac, "running_containers", return_value=running):
                self.ws.sent.clear()
                self.handle(appear(f"k{expect}", launch.STATUS, {"source": "containers"}))
                self.assertIn(expect, svg(self.ws.events("setImage")[0]))


if __name__ == "__main__":
    unittest.main()
