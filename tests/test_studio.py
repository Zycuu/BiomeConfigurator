import copy
import json
from pathlib import Path
import unittest

from worldgen_studio import (
    defaults,
    density,
    noise_settings,
    validate,
    ore_resources,
    TERRAIN_TYPES,
)
from terrain_renderer import voxel_mesh
from fabric_support import default_design, template, build_biome


class StudioTests(unittest.TestCase):
    def test_every_landform_has_a_distinct_exportable_graph(self):
        graphs = []
        for kind in TERRAIN_TYPES[1:]:
            config = defaults()
            config["terrain"] = kind
            graphs.append(json.dumps(density(config), sort_keys=True))
        self.assertEqual(len(graphs), len(set(graphs)))

    def test_cave_type_density_and_height_change_exported_graph(self):
        c = defaults()
        c["terrain"] = "Mountains"
        original = density(c)
        for key, value in (
            ("cave_type", "None"),
            ("cave_density", 0.9),
            ("cave_max_y", 100),
            ("mountain_height", 140),
            ("wavelength", 600),
        ):
            with self.subTest(key=key):
                self.assertNotEqual(original, density(dict(c, **{key: value})))

    def test_terrain_faces_are_axis_aligned_and_cutaway_changes_geometry(self):
        s = json.loads(
            (
                Path(__file__).resolve().parents[1] / "default_terrain_26_3.json"
            ).read_text()
        )
        mesh = voxel_mesh(s, floor_y=32)
        self.assertTrue(mesh)
        for points, normal, y, top in mesh:
            self.assertTrue(
                any(len({p[axis] for p in points}) == 1 for axis in range(3)),
                "A sloping face was generated",
            )
        cut = voxel_mesh(s, cut=0.5, floor_y=32)
        self.assertNotEqual(len(mesh), len(cut))
        layer = voxel_mesh(s, y_limit=33, floor_y=32)
        self.assertTrue(all(32 <= p[1] <= 33 for face in layer for p in face[0]))

    def test_custom_ores_export_distribution_and_vanilla_features_can_be_disabled(self):
        design = default_design()
        c = defaults()
        c.update(
            terrain="Canyons",
            vanilla_ores=False,
            lakes=False,
            geodes=False,
            dungeons=False,
            springs=False,
        )
        ore = {
            "name": "test_ore",
            "block": "minecraft:diamond_ore",
            "count": 8,
            "size": 12,
            "min_y": -56,
            "max_y": 24,
            "discard": 0.5,
            "distribution": "Triangle",
        }
        c["ores"] = [ore]
        design["worldgen"] = c
        biome = build_biome(design, "example", studio=True)
        self.assertEqual(biome["carvers"], [])
        self.assertTrue(build_biome(design, "example")["carvers"])
        for index in (1, 2, 3, 8):
            self.assertEqual(biome["features"][index], [])
        self.assertEqual(biome["features"][6], ["example:bc/gloam_woods/ore_test_ore"])
        feature, placement = ore_resources(ore)
        self.assertEqual(feature["targets"][0]["state"], "minecraft:diamond_ore")
        self.assertEqual(placement[2]["height"]["type"], "minecraft:trapezoid")

    def test_invalid_nan_ore_ids_and_reversed_ranges_are_rejected(self):
        for key, value in (
            ("mountain_height", float("nan")),
            ("cave_min_y", 60),
            ("fluid", "Acid"),
        ):
            with self.assertRaises(ValueError):
                validate(dict(defaults(), **{key: value}))

    def test_noise_settings_preserve_original_and_use_selected_fluid(self):
        source = template("noise_settings")
        original = copy.deepcopy(source)
        c = defaults()
        c.update(terrain="Floating Islands")
        result = noise_settings(source, c)
        self.assertEqual(result["default_fluid"], "minecraft:air")
        self.assertEqual(original, source)


if __name__ == "__main__":
    unittest.main()
