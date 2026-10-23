import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from fabric_support import (FabricProject, build_plan, build_biome, default_design, ROLE_DEFAULTS,
                            texture_image, texture_path, resource_id, MANIFEST)


class ExportTests(unittest.TestCase):
    def setUp(self):
        # Keep fixtures until the test process exits; no user/project files are removed.
        self.root = Path(tempfile.mkdtemp(prefix="bc-fabric-test-"))
        self.project_dir = self.root / "project"
        resources = self.project_dir / "src/main/resources"
        resources.mkdir(parents=True)
        (resources / "fabric.mod.json").write_text(json.dumps({"id": "example", "entrypoints": {"main": ["example.Main"]}, "depends": {"fabricloader": "*"}}))
        (self.project_dir / "build.gradle").write_text("plugins { id 'net.fabricmc.fabric-loom' version '1.18-SNAPSHOT' }\nloom { splitEnvironmentSourceSets() }\n")
        (self.project_dir / "gradle.properties").write_text("minecraft_version=26.3\n")
        self.textures = self.root / "textures"
        self.textures.mkdir()
        for filename in set(ROLE_DEFAULTS.values()):
            Image.new("RGBA", (16, 16), (60, 180, 100, 100 if "leaves" in filename else 255)).save(self.textures / filename)
        (self.textures / "ashwood_leaves.png.mcmeta").write_text('{"texture":{"mipmap_strategy":"dark_cutout"}}')
        self.design = default_design(self.textures)
        self.project = FabricProject.inspect(self.project_dir)

    def test_full_export_wires_project_and_preserves_sources(self):
        original = (self.textures / "duskgrass_block_top.png").read_bytes()
        plan = build_plan(self.project, self.design)
        self.assertGreater(len(plan.changes()), 90)
        backup = plan.apply()
        self.assertEqual((self.textures / "duskgrass_block_top.png").read_bytes(), original)
        self.assertTrue((backup / "originals/build.gradle").is_file())
        mod = json.loads((self.project_dir / "src/main/resources/fabric.mod.json").read_text())
        self.assertEqual(mod["entrypoints"]["main"][0], "example.Main")
        self.assertEqual(len(mod["entrypoints"]["main"]), 2)
        self.assertIn("terrablender", mod["entrypoints"])
        motion=json.loads((self.project_dir / "src/main/resources/data/minecraft/tags/block/blocks_motion.json").read_text())
        self.assertIn("example:gloomstone",motion["values"])
        self.assertIn("include implementation", (self.project_dir / "biome-configurator.gradle").read_text())
        self.assertTrue((self.project_dir / "src/client/java/biomeconfig/generated/m_example/GeneratedClient.java").exists())
        self.assertTrue(any(path.endswith(".png.mcmeta") for path in plan.files))

    def test_repeat_export_is_idempotent(self):
        build_plan(self.project, self.design).apply()
        second = build_plan(FabricProject.inspect(self.project_dir), self.design)
        self.assertEqual(second.changes(), [])
        self.assertIsNone(second.apply())

    def test_updated_design_preserves_previous_biomes(self):
        build_plan(self.project, self.design).apply()
        second = copy.deepcopy(self.design)
        second["biome"] = "ashen_woods"
        second["colors"]["grass_color"] = "#aaaaaa"
        plan = build_plan(FabricProject.inspect(self.project_dir), second)
        plan.apply()
        state = json.loads((self.project_dir / MANIFEST).read_text())
        self.assertEqual(set(state["designs"]), {"gloam_woods", "ashen_woods"})
        java = (self.project_dir / "src/main/java/biomeconfig/generated/m_example/GeneratedContent.java").read_text()
        self.assertEqual(java.count('register("ash_dirt"'), 1)

    def test_existing_unmanaged_model_is_not_overwritten(self):
        target = self.project_dir / "src/main/resources/assets/example/models/block/ash_dirt.json"
        target.parent.mkdir(parents=True)
        target.write_text('{"custom":"keep me"}')
        with self.assertRaisesRegex(ValueError, "existing file"):
            build_plan(self.project, self.design)
        self.assertEqual(target.read_text(), '{"custom":"keep me"}')
        self.assertFalse((self.project_dir / MANIFEST).exists())

    def test_manual_generated_edits_are_preserved(self):
        build_plan(self.project, self.design).apply()
        target = self.project_dir / "src/main/java/biomeconfig/generated/m_example/GeneratedContent.java"
        target.write_text(target.read_text() + "// manual edit\n")
        with self.assertRaisesRegex(ValueError, "edited a generated file"):
            build_plan(FabricProject.inspect(self.project_dir), self.design)

    def test_review_race_is_detected_before_any_writes(self):
        plan = build_plan(self.project, self.design)
        target = self.project_dir / "build.gradle"
        target.write_text(target.read_text() + "// editor changed this\n")
        with self.assertRaisesRegex(ValueError, "after the export review"):
            plan.apply()
        self.assertFalse((self.project_dir / MANIFEST).exists())

    def test_project_metadata_and_custom_names_survive_reexport(self):
        build_plan(self.project, self.design).apply()
        mod_path = self.project_dir / "src/main/resources/fabric.mod.json"
        mod = json.loads(mod_path.read_text())
        mod["description"] = "An unrelated project edit"
        mod_path.write_text(json.dumps(mod, indent=4))
        lang_path = self.project_dir / "src/main/resources/assets/example/lang/en_us.json"
        lang = json.loads(lang_path.read_text())
        lang["block.example.ash_dirt"] = "Zycu's Ash"
        lang_path.write_text(json.dumps(lang, indent=4))
        build = self.project_dir / "build.gradle"
        build.write_text(build.read_text() + "// A new dependency added by the user\n")
        plan = build_plan(FabricProject.inspect(self.project_dir), self.design)
        plan.apply()
        self.assertEqual(json.loads(mod_path.read_text())["description"], mod["description"])
        self.assertEqual(json.loads(lang_path.read_text())["block.example.ash_dirt"], "Zycu's Ash")
        self.assertIn("new dependency", build.read_text())

    def test_partial_failure_restores_originals_and_preserves_new_files(self):
        import fabric_support
        plan = build_plan(self.project, self.design)
        original = (self.project_dir / "build.gradle").read_bytes()
        actual_write = fabric_support.atomic_write
        calls = 0
        def failing_write(path, data):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise OSError("simulated disk failure")
            actual_write(path, data)
        with patch("fabric_support.atomic_write", side_effect=failing_write):
            with self.assertRaisesRegex(OSError, "simulated"):
                plan.apply()
        self.assertEqual((self.project_dir / "build.gradle").read_bytes(), original)
        self.assertFalse((self.project_dir / MANIFEST).exists())
        self.assertTrue(list((self.project_dir / ".biome-configurator-backups").rglob("interrupted-export")))

    def test_26_3_spawn_and_effect_schema(self):
        self.design.update({"mobs": [{"type": "minecraft:pig", "category": "creature", "weight": 10, "minCount": 2,
                                      "maxCount": 4, "energy_budget": 0.12, "charge": 1}],
                            "ambient_particle": "minecraft:ash", "particle_probability": 0.025,
                            "ambient_loop": "minecraft:ambient.soul_sand_valley.loop"})
        biome = build_biome(self.design, "example")
        self.assertNotIn("spawners", biome)
        self.assertNotIn("creature_spawn_probability", biome)
        self.assertNotIn("sky_color", biome["effects"])
        attrs = biome["attributes"]
        spawn = attrs["minecraft:gameplay/natural_mob_spawns"]["argument"]["spawns_by_category"]["creature"][0]
        self.assertEqual(spawn["count"]["max_inclusive"], 4)
        self.assertEqual(attrs["minecraft:visual/ambient_particles"]["modifier"], "append")
        self.assertEqual(attrs["minecraft:audio/ambient_sounds"]["loop"], self.design["ambient_loop"])
        self.assertEqual(len(biome["features"]), 11)

    def test_invalid_inputs_do_not_escape_project(self):
        for value in ("example:../escape", "example:/absolute", "Example:biome", "example:foo//bar", "example:foo\\bar"):
            with self.assertRaises(ValueError): resource_id(value)
        design = copy.deepcopy(self.design)
        design["textures"]["grass_top"] = "../outside.png"
        Image.new("RGB", (16, 16)).save(self.root / "outside.png")
        with self.assertRaisesRegex(ValueError, "inside"):
            texture_path(design, "grass_top")

    def test_grayscale_preserves_alpha_and_does_not_touch_original(self):
        image = texture_image(self.design, "tree1_leaves")
        r, g, b, a = image.getpixel((0, 0))
        self.assertEqual(r, g)
        self.assertEqual(g, b)
        self.assertEqual(a, 100)
        with Image.open(self.textures / "gloom_oak_leaves.png") as original:
            self.assertEqual(original.getpixel((0, 0)), (60, 180, 100, 100))

    def test_other_minecraft_versions_are_rejected(self):
        (self.project_dir / "gradle.properties").write_text("minecraft_version=26.2\n")
        with self.assertRaisesRegex(ValueError, "26.3 only"):
            FabricProject.inspect(self.project_dir)

    def test_gui_review_requires_apply_and_exports_to_selected_project(self):
        import tkinter as tk
        from fabric_app import FabricBiomeConfiguratorApp
        try:
            root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Tk display unavailable: {error}")
        root.withdraw()
        previous_cwd = Path.cwd()
        os.chdir(self.root)
        try:
            app = FabricBiomeConfiguratorApp(root)
            app.set_project(self.project_dir)
            app.set_texture_folder(self.textures)
            root.update()
            app.refresh_palette()
            self.assertIn("Custom palette loaded", app.preview_status.get())
            self.assertIn("tree2_leaves", app.cached_blocks)
            self.assertEqual(len(app.notebook.tabs()), 7)
            with patch("fabric_app.messagebox.showinfo"), patch("fabric_app.messagebox.showerror") as errors:
                app.generate_datapack()
                self.assertFalse((self.project_dir / MANIFEST).exists())
                dialog = next(child for child in root.winfo_children() if isinstance(child, tk.Toplevel))
                buttons = []
                def find_buttons(widget):
                    for child in widget.winfo_children():
                        if isinstance(child, __import__('tkinter.ttk', fromlist=['Button']).Button):
                            buttons.append(child)
                        find_buttons(child)
                find_buttons(dialog)
                next(button for button in buttons if button.cget("text") == "Export with Backups").invoke()
                self.assertTrue((self.project_dir / MANIFEST).exists())
                errors.assert_not_called()
        finally:
            for pending in root.tk.splitlist(root.tk.call("after", "info")):
                root.after_cancel(pending)
            root.destroy()
            os.chdir(previous_cwd)


if __name__ == "__main__":
    unittest.main()
