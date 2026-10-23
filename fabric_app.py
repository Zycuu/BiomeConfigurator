"""Project, palette and export workflow layered over the upstream Tkinter app."""
from pathlib import Path
import copy
import json
import os
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

from PIL import Image, ImageTk
from BiomeConfigurator import BiomeConfiguratorApp
from fabric_support import (FabricProject, ROLE_DEFAULTS, BLOCK_DEFAULTS, default_design,
                            texture_image, is_tinted, build_plan, build_biome, validate_design,
                            valid_path, json_bytes, read_json, MANIFEST)


class FabricBiomeConfiguratorApp(BiomeConfiguratorApp):
    def __init__(self, root):
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure(".", background="#172331", foreground="#dce8f3", font=("Segoe UI", 10))
        style.configure("TNotebook", background="#111b26", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(12, 8), background="#243648")
        style.map("TNotebook.Tab", background=[("selected", "#315875")])
        style.configure("TButton", padding=(10, 6), background="#2b4358")
        style.map("TButton", background=[("active", "#3a617c")])
        style.configure("Accent.TButton", background="#287da6", foreground="white")
        style.configure("TEntry", fieldbackground="#101c29", foreground="#e4edf5", insertcolor="white")
        style.configure("TSpinbox", fieldbackground="#101c29", foreground="#e4edf5", arrowsize=14)
        style.configure("TCombobox", fieldbackground="#101c29", foreground="#e4edf5", arrowsize=14)
        style.map("TCombobox", fieldbackground=[("readonly", "#21394e")], foreground=[("readonly", "#e4edf5")])
        style.configure("Horizontal.TProgressbar", background="#4ab7c9", troughcolor="#101c29")
        root.configure(background="#111b26")
        root.option_add("*TCombobox*Listbox.background", "#172738")
        root.option_add("*TCombobox*Listbox.foreground", "#dce8f3")
        self.project = None
        self.project_path = tk.StringVar(master=root)
        self.texture_dir = tk.StringVar(master=root)
        self.project_status = tk.StringVar(master=root, value="Choose a Minecraft 26.3 Fabric project to begin.")
        self.preview_status = tk.StringVar(master=root, value="Illustration only. The Preview world type tests actual Minecraft generation.")
        self.texture_vars = {role: tk.StringVar(master=root, value=name) for role, name in ROLE_DEFAULTS.items()}
        self.block_vars = {role: tk.StringVar(master=root, value=name) for role, name in BLOCK_DEFAULTS.items()}
        self.tint_grass = tk.BooleanVar(master=root, value=True)
        self.tint_leaves = tk.BooleanVar(master=root, value=True)
        self.generation = {key: tk.StringVar(master=root, value=str(value)) for key, value in {
            "tree1_count": 3, "tree2_count": 2, "plant_count": 12, "region_weight": 2, "deep_y": 0,
            "base_biome": "minecraft:forest"}.items()}
        self.texture_combos = []
        self._refresh_pending = False
        self._palette_stamp = 0
        self.terrain_window = None
        from worldgen_studio import defaults
        self.worldgen_config = defaults()
        super().__init__(root)
        root.title("Biome Configurator Studio | Fabric 26.3")
        root.geometry("1180x980")
        root.minsize(1000, 840)
        self.export_name.set("gloam_woods")
        for variable in [self.tint_grass, self.tint_leaves, *self.texture_vars.values(), *self.generation.values()]:
            variable.trace_add("write", self.request_refresh)
        self.apply_design(default_design())

    def create_layout(self):
        super().create_layout()
        for child in self.root.winfo_children():
            if isinstance(child, ttk.Label) and child.cget("text") == "Live Preview":
                child.config(text="Palette preview: illustrative scene, first animation frame")
            self.relabel_buttons(child)
        self.preview_canvas.config(height=360)
        ttk.Label(self.root, textvariable=self.preview_status, wraplength=1100).pack(fill=tk.X, padx=10)
        project_tab = ttk.Frame(self.notebook, padding=12)
        materials_tab = ttk.Frame(self.notebook)
        generation_tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.insert(0, project_tab, text="Fabric Project")
        self.notebook.insert(1, materials_tab, text="Materials")
        self.notebook.insert(2, generation_tab, text="Generation")
        self.notebook.select(project_tab)
        self.build_project_tab(project_tab)
        self.build_materials_tab(materials_tab)
        self.build_generation_tab(generation_tab)
        ttk.Button(self.root, text="Open Worldgen Studio: Terrain, Caves & Ores...", command=self.open_terrain).pack(fill=tk.X, padx=10, pady=5)

    def open_terrain(self):
        if self.terrain_window is not None:
            self.terrain_window.window.lift()
            return
        from terrain_ui import TerrainWindow
        self.terrain_window = TerrainWindow(self)

    def relabel_buttons(self, widget):
        if isinstance(widget, ttk.Button):
            replacements = {"Generate Datapack": "Review & Export to Fabric", "Export Biome JSON": "Save Biome JSON",
                            "Clear Staging": "Archive Legacy Staging", "Save Preset": "Save Design"}
            text = widget.cget("text")
            if text in replacements:
                widget.config(text=replacements[text])
        for child in widget.winfo_children():
            self.relabel_buttons(child)

    def build_project_tab(self, tab):
        tab.columnconfigure(1, weight=1)
        ttk.Label(tab, text="Fabric project folder:").grid(row=0, column=0, sticky="w", pady=8)
        ttk.Entry(tab, textvariable=self.project_path, state="readonly").grid(row=0, column=1, sticky="ew", padx=8)
        ttk.Button(tab, text="Choose Project...", command=self.choose_project).grid(row=0, column=2)
        ttk.Label(tab, text="Block texture folder:").grid(row=1, column=0, sticky="w", pady=8)
        ttk.Entry(tab, textvariable=self.texture_dir, state="readonly").grid(row=1, column=1, sticky="ew", padx=8)
        ttk.Button(tab, text="Choose Textures...", command=self.choose_textures).grid(row=1, column=2)
        ttk.Label(tab, textvariable=self.project_status, wraplength=1000).grid(row=2, column=0, columnspan=3, sticky="w", pady=12)
        ttk.Label(tab, text=("1. Select your existing Fabric 26.3 project.\n"
                            "2. Select the folder of PNG block textures, then choose them in Materials.\n"
                            "3. Adjust colors and generation. Review & Export installs the generated content.\n"
                            "4. Reload Gradle in your IDE and run Minecraft. Choose the biome's Preview world type\n"
                            "   for a single-biome test, or create a Default world for natural placement.\n\n"
                            "Export adds Java registration, models, textures, tree/plant features, material rules,\n"
                            "a TerraBlender dependency, a preview world type, and a backup of every changed file.\n"
                            "Existing worlds are not regenerated. Use a new test world.\n\n"
                            "First-version scope: two generated oak-shaped tree families and basic terrain/plants.\n"
                            "Grass is a static terrain block; spreading, saplings, and wood crafting are not generated."),
                  justify="left").grid(row=3, column=0, columnspan=3, sticky="w")
        buttons = ttk.Frame(tab)
        buttons.grid(row=4, column=0, columnspan=3, sticky="w", pady=12)
        ttk.Button(buttons, text="Open Design...", command=self.open_design).pack(side="left", padx=4)
        ttk.Button(buttons, text="Load Last Project Design", command=self.load_project_design).pack(side="left", padx=4)
        ttk.Button(buttons, text="Starter Palette", command=lambda: self.apply_design(default_design(self.texture_dir.get()))).pack(side="left", padx=4)

    def build_materials_tab(self, tab):
        canvas = tk.Canvas(tab, highlightthickness=0)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        inside = ttk.Frame(canvas, padding=10)
        window = canvas.create_window((0, 0), window=inside, anchor="nw")
        inside.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        inside.columnconfigure(1, weight=1)
        inside.columnconfigure(3, weight=1)
        ttk.Checkbutton(inside, text="Biome-tinted grass/plants (export grayscale copies)", variable=self.tint_grass).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Checkbutton(inside, text="Biome-tinted leaves (export grayscale copies)", variable=self.tint_leaves).grid(row=0, column=2, columnspan=2, sticky="w")
        ttk.Label(inside, text="Sources are preserved. Untick to keep painted colors. Each tree uses its own selected leaf texture.").grid(row=1, column=0, columnspan=4, sticky="w", pady=8)
        for row, (role, variable) in enumerate(self.texture_vars.items(), start=3):
            ttk.Label(inside, text=role.replace("_", " ").title()).grid(row=row, column=0, sticky="w", padx=5, pady=3)
            combo = ttk.Combobox(inside, textvariable=variable, width=39, state="readonly")
            combo.grid(row=row, column=1, sticky="ew", padx=5)
            self.texture_combos.append(combo)
        ttk.Label(inside, text="Generated block IDs (namespace comes from your project)").grid(row=2, column=2, columnspan=2, sticky="w")
        for row, (role, variable) in enumerate(self.block_vars.items(), start=3):
            ttk.Label(inside, text=role.replace("_", " ").title()).grid(row=row, column=2, sticky="w", padx=12, pady=3)
            ttk.Entry(inside, textvariable=variable, width=27).grid(row=row, column=3, sticky="ew", padx=5)

    def build_generation_tab(self, tab):
        labels = {"tree1_count": "Gloom Oak / first tree attempts per chunk", "tree2_count": "Ashwood / second tree attempts per chunk",
                  "plant_count": "Attempts per chunk for each grass plant", "region_weight": "Overworld region weight (relative, not a percentage)",
                  "deep_y": "Deepstone transition starts at Y", "base_biome": "Use this vanilla biome's climate placement"}
        for row, (key, variable) in enumerate(self.generation.items()):
            ttk.Label(tab, text=labels[key]).grid(row=row, column=0, sticky="w", padx=4, pady=9)
            if key == "base_biome":
                control = ttk.Combobox(tab, textvariable=variable, state="readonly", width=30,
                                       values=["minecraft:forest", "minecraft:dark_forest", "minecraft:taiga", "minecraft:plains"])
            else:
                control = ttk.Spinbox(tab, textvariable=variable, from_=-59 if key == "deep_y" else 0,
                                      to=128 if key == "deep_y" else (100 if key == "region_weight" else 32), width=10)
            control.grid(row=row, column=1, sticky="w", padx=10)
        ttk.Label(tab, text=("Counts are placement attempts, not guaranteed surviving trees.\n"
                            "Open Worldgen Studio to edit landforms, noise caves, ores and feature rules.\n"
                            "Custom shape applies to Preview world presets and optional new dimensions.\n"
                            "Both tree families currently use a configurable palette with vanilla oak-shaped generation."),
                  justify="left").grid(row=7, column=0, columnspan=2, sticky="w", pady=20)

    def choose_project(self):
        folder = filedialog.askdirectory(title="Select your Fabric project folder")
        if folder:
            try:
                self.set_project(folder)
            except Exception as error:
                messagebox.showerror("Cannot open project", str(error), parent=self.root)

    def set_project(self, folder):
        project = FabricProject.inspect(folder)
        self.project = project
        self.project_path.set(str(project.root))
        self.project_status.set(f"Ready: {project.namespace}, Minecraft 26.3, {'split client/main' if project.split_client else 'shared'} sources. Nothing has been exported yet.")
        texture_dir = project.root / f"src/main/resources/assets/{project.namespace}/textures/block"
        if texture_dir.exists() and not self.texture_dir.get():
            self.set_texture_folder(texture_dir)

    def choose_textures(self):
        folder = filedialog.askdirectory(title="Select the folder containing your block PNG textures")
        if folder:
            try: self.set_texture_folder(folder)
            except Exception as error: messagebox.showerror("Cannot open texture folder", str(error), parent=self.root)

    def set_texture_folder(self, folder):
        root = Path(folder).resolve(strict=True)
        files = sorted(path.relative_to(root).as_posix() for path in root.rglob("*.png"))
        self.texture_dir.set(str(root))
        for combo in self.texture_combos:
            combo.configure(values=files)
        self.request_refresh()

    def gather_design(self):
        design = default_design(self.texture_dir.get())
        design.update({"biome": self.export_name.get().strip(), "textures": {key: value.get() for key, value in self.texture_vars.items()},
                       "blocks": {key: value.get().strip() for key, value in self.block_vars.items()},
                       "tint_grass": self.tint_grass.get(), "tint_leaves": self.tint_leaves.get(),
                       "colors": {key: value.get() for key, value in self.colors.items()},
                       "temperature": self.temperature.get(), "downfall": self.downfall.get(), "has_precipitation": self.has_precipitation.get(),
                       "grass_color_modifier": self.grass_modifier.get(), "mobs": copy.deepcopy(self.active_mobs),
                       "ambient_particle": self.ambient_particle.get(), "particle_probability": self.particle_probability.get(),
                       "ambient_loop": self.ambient_loop.get(), "ambient_mood": self.ambient_mood.get(), "ambient_additions": self.ambient_additions.get()})
        for key, value in self.generation.items():
            design[key] = value.get() if key == "base_biome" else int(value.get())
        design["worldgen"] = self.terrain_window.get_config() if self.terrain_window else copy.deepcopy(self.worldgen_config)
        return design

    def apply_design(self, design):
        merged = default_design()
        merged.update(design)
        from worldgen_studio import settings
        self.worldgen_config = settings(merged)
        if self.terrain_window:
            self.terrain_window.load_config(self.worldgen_config)
        self.export_name.set(merged["biome"])
        for key, variable in self.texture_vars.items(): variable.set(merged["textures"].get(key, ROLE_DEFAULTS[key]))
        for key, variable in self.block_vars.items(): variable.set(merged["blocks"].get(key, BLOCK_DEFAULTS[key]))
        self.tint_grass.set(merged["tint_grass"])
        self.tint_leaves.set(merged["tint_leaves"])
        for key, variable in self.generation.items(): variable.set(str(merged[key]))
        for key, variable in self.colors.items(): variable.set(merged["colors"][key])
        for key in ("temperature", "downfall", "has_precipitation", "grass_color_modifier", "ambient_particle", "particle_probability", "ambient_loop", "ambient_mood", "ambient_additions"):
            variable = self.grass_modifier if key == "grass_color_modifier" else getattr(self, key)
            variable.set(merged[key])
        self.active_mobs = copy.deepcopy(merged.get("mobs", []))
        self.update_mob_listbox()
        self.texture_dir.set(merged["texture_dir"])
        if merged["texture_dir"] and Path(merged["texture_dir"]).is_dir():
            self.set_texture_folder(merged["texture_dir"])
        self.request_refresh()

    def save_custom_preset(self):
        try:
            design = self.gather_design()
            valid_path(design["biome"])
            path = filedialog.asksaveasfilename(title="Save biome design", defaultextension=".json", initialfile=design["biome"] + ".biome-design.json", filetypes=[("Biome design", "*.json")])
            if path:
                Path(path).write_bytes(json_bytes(design))
        except Exception as error:
            messagebox.showerror("Cannot save design", str(error), parent=self.root)

    def open_design(self):
        path = filedialog.askopenfilename(title="Open biome design", filetypes=[("Biome design", "*.json")])
        if path:
            try: self.apply_design(read_json(path))
            except Exception as error: messagebox.showerror("Cannot open design", str(error), parent=self.root)

    def load_project_design(self):
        if not self.project:
            messagebox.showinfo("Select a project", "Choose a Fabric project first.", parent=self.root)
            return
        try:
            designs = read_json(self.project.root / MANIFEST)["designs"]
            self.apply_design(list(designs.values())[-1])
        except Exception as error:
            messagebox.showerror("No saved project design", str(error), parent=self.root)

    def export_json(self):
        try:
            if not self.project: raise ValueError("Choose your Fabric project first so the namespace is correct.")
            design = self.gather_design()
            validate_design(design)
            path = filedialog.asksaveasfilename(title="Save Minecraft 26.3 biome JSON", defaultextension=".json", initialfile=design["biome"] + ".json")
            if path: Path(path).write_bytes(json_bytes(build_biome(design, self.project.namespace)))
        except Exception as error:
            messagebox.showerror("Cannot export biome", str(error), parent=self.root)

    def generate_datapack(self):
        try:
            if not self.project: raise ValueError("Choose a Minecraft 26.3 Fabric project first.")
            plan = build_plan(self.project, self.gather_design())
            self.review_export(plan)
        except Exception as error:
            messagebox.showerror("Export stopped", str(error), parent=self.root)

    def review_export(self, plan):
        dialog = tk.Toplevel(self.root)
        dialog.title("Review Fabric export")
        dialog.geometry("920x660")
        ttk.Label(dialog, text=f"Project: {plan.project.root}\n{len(plan.changes())} file changes. Every changed existing file will be backed up.", wraplength=880).pack(padx=12, pady=12, anchor="w")
        text = tk.Text(dialog, wrap="none")
        text.pack(fill="both", expand=True, padx=12)
        text.insert("1.0", "\n".join(f"{action:6}  {path}" for action, path in plan.changes()))
        text.configure(state="disabled")
        ttk.Label(dialog, text="This updates fabric.mod.json and adds a Gradle dependency. Reload Gradle afterward.\nUse a new test world. Existing worlds and source textures are not changed.").pack(pady=10)
        def apply():
            try:
                backup = plan.apply()
                dialog.destroy()
                self.project_status.set("Export complete. Reload Gradle, run Minecraft, and create a new Preview world.")
                messagebox.showinfo("Export complete", f"Content installed.\nBackup: {backup or 'No changes needed'}\n\nReload Gradle in IntelliJ, then run Minecraft.\nChoose the biome's Preview world type for testing.", parent=self.root)
            except Exception as error:
                messagebox.showerror("Export stopped", str(error), parent=dialog)
        buttons = ttk.Frame(dialog)
        buttons.pack(pady=12)
        ttk.Button(buttons, text="Export with Backups", command=apply).pack(side="left", padx=10)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=10)
        dialog.transient(self.root)
        dialog.grab_set()

    def clear_staging(self):
        staging = Path("output/data")
        if staging.exists():
            archive = staging.with_name("data-archived-" + datetime.now().strftime("%Y%m%d-%H%M%S-%f"))
            staging.rename(archive)
            messagebox.showinfo("Archived", f"Legacy staging preserved at {archive.resolve()}", parent=self.root)
        else:
            messagebox.showinfo("No legacy staging", "Fabric exports go directly to the chosen project after review.", parent=self.root)

    def request_refresh(self, *args):
        if not self._refresh_pending and hasattr(self, "preview_canvas"):
            self._refresh_pending = True
            self.root.after_idle(self.refresh_palette)

    def refresh_palette(self):
        self._refresh_pending = False
        self._palette_stamp += 1
        self.last_colors = None
        try:
            self.generate_3d_scene()
            self.update_preview()
        except (ValueError, tk.TclError):
            self.preview_status.set("Finish entering a number to update the preview.")

    def generate_3d_scene(self):
        self.scene_blocks = []
        for x in range(10):
            for z in range(10):
                if (x in (0, 9)) and (z in (0, 9)): continue
                self.scene_blocks.extend([(x, -2, z, "deepstone"), (x, -1, z, "stone"), (x, 0, z, "dirt")])
                water = x >= 7 and z <= 2
                self.scene_blocks.append((x, 1, z, "water" if water else "grass"))
        occupied = set()
        for tree, positions in (("tree1", [(2, 4), (4, 7), (2, 8)]), ("tree2", [(7, 6), (6, 3), (8, 8)])):
            try: count = int(self.generation[tree + "_count"].get())
            except ValueError: count = 0
            if count <= 0: continue
            for x, z in positions[:min(3, (count + 2) // 3)]:
                occupied.add((x, z))
                for y in range(2, 6): self.scene_blocks.append((x, y, z, tree + "_log"))
                for dx in range(-1, 2):
                    for dz in range(-1, 2): self.scene_blocks.append((x + dx, 6, z + dz, tree + "_leaves"))
                self.scene_blocks.append((x, 7, z, tree + "_leaves"))
        try: count = min(int(self.generation["plant_count"].get()), 28)
        except ValueError: count = 0
        rng = random.Random(416)
        for i in range(count):
            x, z = rng.randrange(1, 9), rng.randrange(3, 9)
            if (x, z) in occupied: continue
            occupied.add((x, z))
            kind = ("short_grass", "dusk_grass", "tall_grass")[i % 3]
            self.scene_blocks.append((x, 2, z, kind))
        self.scene_blocks.sort(key=lambda block: (block[0] + block[2], block[1], block[0]))

    def draw_scene(self, origin_x, origin_y, tile_w, tile_h, block_h):
        for x, y, z, block_type in self.scene_blocks:
            if block_type not in getattr(self, "cached_blocks", {}): continue
            sx = origin_x + (x - z) * tile_w
            sy = origin_y + (x + z) * tile_h - y * block_h - tile_h
            if block_type == "tall_grass": sy -= 30
            self.preview_canvas.create_image(sx, sy, image=self.cached_blocks[block_type], anchor=tk.N, tags="static")

    def regenerate_textures(self):
        if not self.texture_dir.get():
            super().regenerate_textures()
            # Fill new scene roles with upstream neutral placeholders until a palette is selected.
            for name in ("stone", "deepstone", "dirt"): self.cached_blocks[name] = self.cached_blocks["grass"]
            for tree in ("tree1", "tree2"):
                self.cached_blocks[tree + "_log"] = self.cached_blocks["wood"]
                self.cached_blocks[tree + "_leaves"] = self.cached_blocks["leaves"]
            return
        try:
            design = self.gather_design()
            images = {role: texture_image(design, role, preview=True) for role in ROLE_DEFAULTS}
            for role, image in images.items():
                if is_tinted(design, role):
                    key = "foliage_color" if role.endswith("_leaves") else "grass_color"
                    images[role] = self.apply_color(image, design["colors"][key])
            side = images["grass_side"].copy()
            side.alpha_composite(images["grass_overlay"])
            cache = {"grass": self.build_iso_block(images["grass_top"], side, side)}
            for name in ("dirt", "stone", "deepstone"):
                cache[name] = self.build_iso_block(images[name], images[name], images[name])
            water = self.apply_color(self.tex_water, design["colors"]["water_color"])
            cache["water"] = self.build_iso_block(water, water, water)
            for tree in ("tree1", "tree2"):
                bark, top, leaves = images[tree + "_log"], images[tree + "_top"], images[tree + "_leaves"]
                cache[tree + "_log"] = self.build_iso_block(top, bark, bark)
                cache[tree + "_leaves"] = self.build_iso_block(leaves, leaves, leaves)
            for name in ("short_grass", "dusk_grass"):
                cache[name] = images[name].resize((30, 30), Image.Resampling.NEAREST)
            tall = Image.new("RGBA", (16, 32))
            tall.paste(images["tall_top"], (0, 0))
            tall.paste(images["tall_bottom"], (0, 16))
            cache["tall_grass"] = tall.resize((30, 60), Image.Resampling.NEAREST)
            self.cached_blocks = {key: ImageTk.PhotoImage(image, master=self.root) for key, image in cache.items()}
            self.preview_status.set("Custom palette loaded. Illustration only; animations show their first frame. Use the Preview world for exact results.")
        except (OSError, ValueError, KeyError) as error:
            self.preview_status.set(f"Preview needs attention: {error}")
