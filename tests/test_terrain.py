import copy
import json
from pathlib import Path
import tempfile
import threading
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from terrain_sampler import (
    SampleRequest,
    SampleCancelled,
    minecraft_seed,
    validate_sample,
    sample_terrain,
)
from terrain_renderer import TerrainRenderer, clip_water

ROOT = Path(__file__).resolve().parents[1]


class TerrainTests(unittest.TestCase):
    def setUp(self):
        self.sample = json.loads((ROOT / "default_terrain_26_3.json").read_text())

    def test_seeds_follow_java_signed_long_and_utf16_hash(self):
        self.assertEqual(minecraft_seed("-9223372036854775808"), -(1 << 63))
        self.assertEqual(minecraft_seed("Minecraft"), -1595926131)
        self.assertEqual(minecraft_seed("😀"), 1772899)
        with self.assertRaises(ValueError):
            minecraft_seed("")

    def test_bounds_and_grid_are_validated_before_launch(self):
        for request in (
            SampleRequest(center_x=30000000),
            SampleRequest(span=17),
            SampleRequest(grid=12),
            SampleRequest(seed=1 << 63),
        ):
            with self.assertRaises(ValueError):
                request.validate()

    def test_truncated_or_mismatched_sample_is_rejected(self):
        validate_sample(self.sample)
        bad = copy.deepcopy(self.sample)
        bad["heights"][0].pop()
        with self.assertRaises(ValueError):
            validate_sample(bad)
        for key, value in (
            ("minecraft", "1.21"),
            ("max_height", 999),
            ("origin_x", 234),
        ):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_sample(dict(self.sample, **{key: value}))

    def test_water_shoreline_is_clipped_to_submerged_triangle(self):
        polygon = clip_water([(0, 60, 0), (10, 70, 0), (0, 70, 10)], 65)
        self.assertEqual(len(polygon), 3)
        self.assertTrue(all(p[1] == 65 for p in polygon))
        self.assertIn((5.0, 65, 0.0), polygon)
        self.assertIn((0.0, 65, 5.0), polygon)
        self.assertEqual(clip_water([(0, 70, 0), (10, 70, 0), (0, 70, 10)], 65), [])

    def test_camera_and_palette_change_render_without_mutating_heights(self):
        original = copy.deepcopy(self.sample)
        renderer = TerrainRenderer()
        first = renderer.render(self.sample, (640, 400), {}, trees=False)
        renderer.yaw += 1
        second = renderer.render(self.sample, (640, 400), {}, trees=False)
        third = renderer.render(
            self.sample, (640, 400), {"grass": (250, 30, 40)}, trees=False
        )
        self.assertNotEqual(first.tobytes(), second.tobytes())
        self.assertNotEqual(second.tobytes(), third.tobytes())
        self.assertEqual(original, self.sample)

    def test_viewer_tracks_palette_orbit_zoom_and_unregisters_on_close(self):
        from fabric_app import FabricBiomeConfiguratorApp

        root = tk.Tk()
        root.withdraw()
        try:
            app = FabricBiomeConfiguratorApp(root)
            app.open_terrain()
            root.update()
            view = app.terrain_window
            view.render()
            first = view.last_image.tobytes()
            app.colors["grass_color"].set("#ee2222")
            view.render()
            self.assertNotEqual(first, view.last_image.tobytes())
            view.start_drag(SimpleNamespace(x=10, y=10))
            view.orbit(SimpleNamespace(x=50, y=30))
            self.assertNotEqual(view.renderer.yaw, -0.72)
            view.zoom(SimpleNamespace(delta=120))
            self.assertGreater(view.renderer.zoom, 1)
            variables = [variable for variable, _ in view.traces]
            before = [len(variable.trace_info()) for variable in variables]
            view.close()
            self.assertTrue(view.cancel.is_set())
            self.assertEqual(
                [len(variable.trace_info()) for variable in variables],
                [count - 1 for count in before],
            )
            self.assertIsNone(app.terrain_window)
        finally:
            for pending in root.tk.splitlist(root.tk.call("after", "info")):
                root.after_cancel(pending)
            root.destroy()

    def test_cancel_stops_only_our_sampler_process(self):
        cancel = threading.Event()
        cancel.set()
        process = unittest.mock.Mock()
        process.poll.return_value = None
        with patch(
            "terrain_sampler.discover_runtime",
            return_value=(Path("java"), [Path("bridge.jar")]),
        ), patch("terrain_sampler.subprocess.Popen", return_value=process):
            with self.assertRaises(SampleCancelled):
                sample_terrain(SampleRequest(), Path(tempfile.mkdtemp()), cancel=cancel)
        process.terminate.assert_called_once()
        process.wait.assert_called_once()


if __name__ == "__main__":
    unittest.main()
