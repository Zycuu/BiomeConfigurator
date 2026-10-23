"""Orbitable, asynchronous Minecraft terrain preview for the Fabric editor."""

import json
import os
from pathlib import Path
import queue
import threading
import copy
import time
from worldgen_studio import defaults, settings, validate, TERRAIN_TYPES, CAVE_TYPES
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

from fabric_support import texture_image, is_tinted
from terrain_sampler import (
    SampleRequest,
    SampleCancelled,
    minecraft_seed,
    sample_terrain,
    validate_sample,
)
from terrain_renderer import TerrainRenderer, rgb


class TerrainWindow:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("Worldgen Studio | Fabric 26.3")
        self.window.geometry("1440x920")
        self.window.minsize(1120, 650)
        self.renderer = TerrainRenderer()
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.pending = None
        self.poll_id = None
        self.traces = []
        self.sample = validate_sample(
            json.loads(
                Path(__file__).with_name("default_terrain_26_3.json").read_text()
            )
        )
        self.seed = tk.StringVar(value=self.sample["seed"])
        self.x = tk.StringVar(value=str(self.sample["center_x"]))
        self.z = tk.StringVar(value=str(self.sample["center_z"]))
        self.span = tk.StringVar(value="64")
        self.detail = tk.StringVar(value="65")
        self.water = tk.BooleanVar(value=True)
        self.trees = tk.BooleanVar(value=True)
        self.wire = tk.BooleanVar(value=False)
        self.exaggeration = tk.DoubleVar(value=1)
        self.status = tk.StringVar(
            value="Ready. Generate to sample your current terrain and cave settings."
        )
        config = copy.deepcopy(getattr(app, "worldgen_config", defaults()))
        self.config_vars = {
            key: tk.StringVar(value=str(value))
            for key, value in config.items()
            if key not in ("ores",)
        }
        self.ores = copy.deepcopy(config["ores"])
        self.mode = tk.StringVar(value="Surface")
        self.slice_y = tk.DoubleVar(value=32)
        self.auto = tk.BooleanVar(value=False)
        self.auto_id = None
        self.generating_config = None
        self.info = tk.StringVar()
        self.build_layout()
        self.update_sample_info()
        variables = [
            self.water,
            self.trees,
            self.wire,
            self.exaggeration,
            app.tint_grass,
            app.tint_leaves,
            *app.colors.values(),
            *app.texture_vars.values(),
            *app.generation.values(),
            app.texture_dir,
        ]
        for variable in variables:
            token = variable.trace_add("write", self.request_render)
            self.traces.append((variable, token))
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.bind("<Destroy>", self.on_destroy, add=True)
        for variable in [
            *self.config_vars.values(),
            self.seed,
            self.x,
            self.z,
            self.span,
            self.detail,
        ]:
            token = variable.trace_add("write", self.mark_dirty)
            self.traces.append((variable, token))
        for variable in (self.mode, self.slice_y):
            token = variable.trace_add("write", self.request_render)
            self.traces.append((variable, token))
        self.poll_id = self.window.after(100, self.poll)
        self.request_render()

    def on_destroy(self, event):
        if event.widget is self.window:
            self.cancel.set()

    def get_config(self):
        config = defaults()
        for key, variable in self.config_vars.items():
            value = variable.get()
            if isinstance(config[key], bool):
                config[key] = value.lower() in ("true", "1")
            elif isinstance(config[key], int):
                config[key] = int(value)
            elif isinstance(config[key], float):
                config[key] = float(value)
            else:
                config[key] = value
        config["ores"] = copy.deepcopy(self.ores)
        return validate(config)

    def load_config(self, config):
        for key, variable in self.config_vars.items():
            variable.set(str(config[key]))
        self.ores = copy.deepcopy(config["ores"])
        self.refresh_ores()

    def mark_dirty(self, *args):
        try:
            self.app.worldgen_config = self.get_config()
            self.status.set(
                "Worldgen edits pending. Generate Terrain to preview the edited settings. Save Design retains them."
            )
            self.ore_chart()
        except ValueError as error:
            self.status.set(str(error))
            return
        if self.auto_id:
            self.window.after_cancel(self.auto_id)
        if self.auto.get():
            self.auto_id = self.window.after(1000, self.auto_generate)

    def auto_generate(self):
        self.auto_id = None
        if self.worker and self.worker.is_alive():
            self.auto_id = self.window.after(1000, self.auto_generate)
        else:
            self.generate()

    def build_layout(self):
        top = ttk.Frame(self.window, padding=10)
        top.pack(fill="x")
        ttk.Label(top, text="WORLDGEN STUDIO", font=("Segoe UI", 14, "bold")).pack(
            side="left", padx=(4, 20)
        )
        for label, variable, width in [
            ("Seed", self.seed, 16),
            ("X", self.x, 7),
            ("Z", self.z, 7),
        ]:
            ttk.Label(top, text=label).pack(side="left", padx=(7, 3))
            ttk.Entry(top, textvariable=variable, width=width).pack(side="left")
        for label, variable, values in [
            ("Area", self.span, (32, 64, 128, 256, 512, 1024)),
            ("Grid", self.detail, (33, 65, 129)),
        ]:
            ttk.Label(top, text=label).pack(side="left", padx=(9, 3))
            ttk.Combobox(
                top, textvariable=variable, values=values, width=5, state="readonly"
            ).pack(side="left")
        self.generate_button = ttk.Button(
            top, text="Generate Terrain", command=self.generate, style="Accent.TButton"
        )
        self.generate_button.pack(side="left", padx=12)
        self.cancel_button = ttk.Button(
            top, text="Cancel", command=self.cancel.set, state="disabled"
        )
        self.cancel_button.pack(side="left")
        body = ttk.Panedwindow(self.window, orient="horizontal")
        body.pack(fill="both", expand=True, padx=10)
        side = ttk.Frame(body, width=350)
        view = ttk.Frame(body)
        body.add(side, weight=0)
        body.add(view, weight=1)
        notebook = ttk.Notebook(side)
        notebook.pack(fill="both", expand=True)
        tabs = {}
        scroll_canvases = {}
        for name in ("Terrain", "Caves", "Ores", "Features", "Export"):
            outer = ttk.Frame(notebook)
            notebook.add(outer, text=name)
            canvas = tk.Canvas(
                outer, background="#172331", highlightthickness=0, width=330
            )
            scroll = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
            canvas.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)
            tab = ttk.Frame(canvas, padding=12)
            window = canvas.create_window(0, 0, anchor="nw", window=tab)
            tab.bind(
                "<Configure>",
                lambda event, c=canvas: c.configure(scrollregion=c.bbox("all")),
            )
            canvas.bind(
                "<Configure>",
                lambda event, c=canvas, w=window: c.itemconfigure(w, width=event.width),
            )
            tabs[name] = tab
            scroll_canvases[str(outer)] = canvas

        def sidebar_wheel(event):
            if (
                side.winfo_rootx()
                <= event.x_root
                < side.winfo_rootx() + side.winfo_width()
            ):
                scroll_canvases[notebook.select()].yview_scroll(
                    -1 if event.delta > 0 else 1, "units"
                )

        self.window.bind("<MouseWheel>", sidebar_wheel, add=True)
        tab = tabs["Terrain"]
        ttk.Label(tab, text="Landform", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        chooser = ttk.Combobox(
            tab,
            textvariable=self.config_vars["terrain"],
            values=TERRAIN_TYPES,
            state="readonly",
            width=30,
        )
        chooser.pack(fill="x", pady=8)
        chooser.bind("<<ComboboxSelected>>", self.choose_landform)
        for label, key, low, high in [
            ("Base elevation (Y)", "base_height", -32, 224),
            ("Relief amplitude (blocks)", "mountain_height", 0, 160),
            ("Landform wavelength (blocks)", "wavelength", 32, 2048),
            ("Surface detail (blocks)", "detail", 0, 32),
            ("Sea level (Y)", "sea_level", -60, 160),
            ("Plateau step height", "terrace_height", 4, 64),
            ("Floating island thickness", "island_thickness", 8, 96),
        ]:
            self.number(tab, label, key, low, high)
        ttk.Label(
            tab,
            text="""Relief is an amplitude, not an exact maximum peak. Wavelength controls the spacing of hills, ridges or islands.

Vanilla Overworld keeps the original density graph. Choose a custom landform to edit shape and noise caves.""",
            wraplength=285,
        ).pack(anchor="w", pady=10)
        ttk.Button(
            tab, text="Far Dark Highlands preset", command=self.far_dark_preset
        ).pack(fill="x", pady=5)
        ttk.Label(tab, text="Sea fluid").pack(anchor="w", pady=(8, 2))
        ttk.Combobox(
            tab,
            textvariable=self.config_vars["fluid"],
            values=("Water", "Lava", "Air"),
            state="readonly",
        ).pack(fill="x")
        tab = tabs["Caves"]
        ttk.Label(tab, text="Noise cave system", font=("Segoe UI", 11, "bold")).pack(
            anchor="w"
        )
        ttk.Combobox(
            tab,
            textvariable=self.config_vars["cave_type"],
            values=CAVE_TYPES,
            state="readonly",
        ).pack(fill="x", pady=8)
        for label, key, low, high, increment in [
            ("Cave density", "cave_density", 0, 1, 0.05),
            ("Cave size multiplier", "cave_size", 0.25, 4, 0.25),
            ("Minimum cave Y", "cave_min_y", -60, 240, 1),
            ("Maximum cave Y", "cave_max_y", -56, 280, 1),
        ]:
            self.number(tab, label, key, low, high, increment)
        ttk.Label(
            tab,
            text="""Tunnels follow intersecting spaghetti noise. Chambers create larger cavities. Mixed combines both.

These controls apply to custom landforms. Vanilla Overworld retains stock noise caves. Custom worlds omit vanilla carvers, so they do not add hidden tunnels after this preview.

Use Half cutaway or Horizontal slice to inspect underground space. Generate again after edits.""",
            wraplength=285,
        ).pack(anchor="w", pady=14)
        tab = tabs["Ores"]
        ttk.Checkbutton(
            tab,
            text="Keep vanilla underground features",
            variable=self.config_vars["vanilla_ores"],
            onvalue="True",
            offvalue="False",
        ).pack(anchor="w")
        self.ore_list = tk.Listbox(
            tab,
            height=7,
            background="#172738",
            foreground="#dce9f5",
            selectbackground="#28678c",
            exportselection=False,
        )
        self.ore_list.pack(fill="x", pady=8)
        self.ore_list.bind("<<ListboxSelect>>", self.select_ore)
        self.ore_vars = {
            k: tk.StringVar(value=str(v))
            for k, v in {
                "name": "diamond",
                "block": "minecraft:diamond_ore",
                "count": 6,
                "size": 8,
                "min_y": -56,
                "max_y": 16,
                "distribution": "Triangle",
                "discard": 0.5,
            }.items()
        }
        for key, label in [
            ("name", "Rule name"),
            ("block", "Registered block ID"),
            ("count", "Attempts / chunk"),
            ("size", "Vein size"),
            ("min_y", "Minimum Y"),
            ("max_y", "Maximum Y"),
            ("discard", "Air exposure discard"),
        ]:
            row = ttk.Frame(tab)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label).pack(side="left")
            if key == "block":
                ttk.Combobox(
                    row,
                    textvariable=self.ore_vars[key],
                    width=24,
                    values=[
                        f"minecraft:{name}_ore"
                        for name in (
                            "coal",
                            "iron",
                            "copper",
                            "gold",
                            "redstone",
                            "lapis",
                            "diamond",
                            "emerald",
                        )
                    ],
                ).pack(side="right")
            else:
                ttk.Entry(row, textvariable=self.ore_vars[key], width=14).pack(
                    side="right"
                )
        ttk.Combobox(
            tab,
            textvariable=self.ore_vars["distribution"],
            values=("Uniform", "Triangle"),
            state="readonly",
        ).pack(fill="x", pady=5)
        row = ttk.Frame(tab)
        row.pack(fill="x")
        ttk.Button(row, text="Add / Update", command=self.upsert_ore).pack(side="left")
        ttk.Button(row, text="Remove rule", command=self.remove_ore).pack(side="right")
        self.chart = tk.Canvas(
            tab, height=140, background="#111b26", highlightthickness=0
        )
        self.chart.pack(fill="x", pady=10)
        ttk.Label(
            tab,
            text="Chart: vertical attempt distribution, not exact ore locations. Block IDs must exist in your mod or Minecraft. Vein size is an upper placement budget, not guaranteed output. Removing a rule edits this design only.",
            wraplength=285,
        ).pack(anchor="w")
        tab = tabs["Features"]
        ttk.Label(
            tab,
            text="Decoration and underground features",
            font=("Segoe UI", 11, "bold"),
            wraplength=285,
        ).pack(anchor="w", pady=8)
        for key, label in (
            ("lakes", "Vanilla lava lakes"),
            ("geodes", "Amethyst geodes"),
            ("dungeons", "Vanilla monster rooms"),
            ("springs", "Water and lava springs"),
        ):
            ttk.Checkbutton(
                tab,
                text=label,
                variable=self.config_vars[key],
                onvalue="True",
                offvalue="False",
            ).pack(anchor="w", pady=7)
        for key, label in (
            ("tree1_count", "First tree attempts / chunk"),
            ("tree2_count", "Second tree attempts / chunk"),
            ("plant_count", "Plant attempts / chunk"),
        ):
            ttk.Label(tab, text=label).pack(anchor="w", pady=(10, 3))
            ttk.Spinbox(
                tab, textvariable=self.app.generation[key], from_=0, to=32, width=12
            ).pack(anchor="w")
        ttk.Label(
            tab,
            text="Feature settings export into the biome, including natural Overworld placement. Trees in this viewport illustrate density. Geodes, dungeons, springs and final decorations are checked in Minecraft, not simulated here.",
            wraplength=285,
        ).pack(anchor="w", pady=15)
        ttk.Button(
            tab,
            text="Edit materials in main editor",
            command=lambda: (self.app.notebook.select(1), self.app.root.lift()),
        ).pack(fill="x", pady=8)
        tab = tabs["Export"]
        ttk.Label(
            tab, text="From design to your mod", font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=8)
        ttk.Label(
            tab,
            text="""1. Choose project and materials in the main editor.
2. Set terrain, caves, ore rules and biome atmosphere.
3. Generate and inspect the terrain/cutaway.
4. Save Design, then Review & Export.
5. Reload Gradle and create a NEW Preview world.

Terrain settings are exported to this biome's Preview world preset. Natural placement in the normal Overworld uses its existing terrain.

Optionally create a separate dimension using this generator. Existing unmanaged dimensions are protected by export preflight.""",
            wraplength=285,
        ).pack(anchor="w", pady=8)
        ttk.Checkbutton(
            tab,
            text="Also export a new dimension",
            variable=self.config_vars["dimension"],
            onvalue="True",
            offvalue="False",
        ).pack(anchor="w", pady=8)
        ttk.Entry(tab, textvariable=self.config_vars["dimension_id"]).pack(fill="x")
        ttk.Label(
            tab,
            text="Dimension path only, such as gloam_woods_world. Namespace comes from your project. Uses Overworld dimension physics; existing Far Dark clocks/lighting are not copied.",
            wraplength=285,
        ).pack(anchor="w", pady=8)
        ttk.Button(
            tab, text="Save Design...", command=self.app.save_custom_preset
        ).pack(fill="x", pady=6)
        ttk.Button(
            tab, text="Review & Export to Fabric...", command=self.app.generate_datapack
        ).pack(fill="x", pady=6)
        toolbar = ttk.Frame(view, padding=(8, 0, 4, 8))
        toolbar.pack(fill="x")
        ttk.Combobox(
            toolbar,
            textvariable=self.mode,
            values=("Surface", "Half cutaway", "Horizontal slice"),
            state="readonly",
            width=16,
        ).pack(side="left", padx=3)
        for label, var in [
            ("Water", self.water),
            ("Trees*", self.trees),
            ("Mesh", self.wire),
        ]:
            ttk.Checkbutton(toolbar, text=label, variable=var).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Reset", command=self.reset).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Top", command=self.top_view).pack(side="left", padx=3)
        ttk.Button(toolbar, text="Save PNG", command=self.save_image).pack(
            side="left", padx=3
        )
        ttk.Label(view, textvariable=self.info, padding=(10, 3)).pack(fill="x")
        self.canvas = tk.Canvas(view, background="#111b26", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        for event, callback in [
            ("<Configure>", self.request_render),
            ("<ButtonPress-1>", self.start_drag),
            ("<B1-Motion>", self.orbit),
            ("<ButtonPress-3>", self.start_drag),
            ("<B3-Motion>", self.pan),
            ("<MouseWheel>", self.zoom),
        ]:
            self.canvas.bind(event, callback)
        slice_bar = ttk.Frame(view, padding=8)
        slice_bar.pack(fill="x")
        ttk.Label(slice_bar, text="Slice Y").pack(side="left")
        ttk.Scale(slice_bar, from_=-60, to=260, variable=self.slice_y).pack(
            side="left", fill="x", expand=True, padx=8
        )
        ttk.Checkbutton(
            slice_bar, text="Auto regenerate edits", variable=self.auto
        ).pack(side="left", padx=5)
        self.progress = ttk.Progressbar(self.window, maximum=100)
        self.progress.pack(fill="x", padx=10, pady=(5, 0))
        ttk.Label(
            self.window, textvariable=self.status, padding=(16, 4), wraplength=1380
        ).pack(fill="x")
        ttk.Label(
            self.window,
            text="""Left drag: orbit | Right drag: pan | Wheel: zoom | Samples at 1-block spacing show true block geometry. Larger spacing is coarse.
Noise terrain/caves are sampled by Minecraft. Trees are illustrative; ores are distribution charts. Surface finishing, carvers and structures are not rendered.""",
            padding=(16, 4),
            wraplength=1380,
        ).pack(fill="x")
        self.refresh_ores()

    def number(self, parent, label, key, low, high, increment=1):
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=5)
        ttk.Label(row, text=label).pack(side="left")
        ttk.Spinbox(
            row,
            textvariable=self.config_vars[key],
            from_=low,
            to=high,
            increment=increment,
            width=9,
        ).pack(side="right")

    def far_dark_preset(self):
        from worldgen_studio import preset

        c = preset("Ridged Highlands")
        c.update(
            sea_level=28,
            cave_type="Mixed",
            cave_density=0.55,
            vanilla_ores=False,
            lakes=False,
            springs=False,
        )
        self.load_config(c)
        self.span.set("128")
        self.detail.set("129")

    def choose_landform(self, event=None):
        from worldgen_studio import preset

        config = preset(self.config_vars["terrain"].get())
        old = self.get_config()
        for key in (
            "ores",
            "dimension",
            "dimension_id",
            "vanilla_ores",
            "lakes",
            "geodes",
            "dungeons",
            "springs",
        ):
            config[key] = old[key]
        self.load_config(config)
        if config["terrain"] != "Flatlands":
            self.span.set("128")
            self.detail.set("129")

    def refresh_ores(self):
        self.ore_list.delete(0, "end")
        for ore in self.ores:
            self.ore_list.insert(
                "end",
                f"{ore['name']}  | {ore['count']}/chunk | Y {ore['min_y']}..{ore['max_y']}",
            )
        self.ore_chart()

    def select_ore(self, event=None):
        selected = self.ore_list.curselection()
        if selected:
            for key, value in self.ores[selected[0]].items():
                self.ore_vars[key].set(str(value))

    def upsert_ore(self):
        try:
            ore = {k: v.get().strip() for k, v in self.ore_vars.items()}
            for k in ("count", "size", "min_y", "max_y"):
                ore[k] = int(ore[k])
            ore["discard"] = float(ore["discard"])
            config = self.get_config()
            config["ores"] = [o for o in self.ores if o["name"] != ore["name"]] + [ore]
            validate(config)
            self.ores = config["ores"]
            self.refresh_ores()
            self.mark_dirty()
        except ValueError as error:
            messagebox.showerror("Ore rule", str(error), parent=self.window)

    def remove_ore(self):
        selected = self.ore_list.curselection()
        if selected:
            self.ores.pop(selected[0])
            self.refresh_ores()
            self.mark_dirty()

    def ore_chart(self):
        if not hasattr(self, "chart"):
            return
        c = self.chart
        c.delete("all")
        width = max(280, c.winfo_width())
        height = 140
        c.create_text(8, 8, text="ATTEMPTS BY HEIGHT", anchor="nw", fill="#9fbad1")
        for index, ore in enumerate(self.ores):
            color = ("#56c8de", "#d5a965", "#a391ef", "#7fb77b")[index % 4]
            points = []
            lo, hi = ore["min_y"], ore["max_y"]
            for i in range(65):
                y = lo + (hi - lo) * i / 64
                amount = (
                    1
                    if ore["distribution"] == "Uniform"
                    else max(0, 1 - abs(i / 32 - 1))
                )
                points.extend(
                    (
                        20 + (y + 64) / 384 * (width - 40),
                        120 - amount * min(90, ore["count"] * 6),
                    )
                )
            c.create_line(*points, fill=color, width=2)
        c.create_text(
            12,
            130,
            text="-64                       Y                       320",
            anchor="w",
            fill="#839bb1",
        )

    def update_sample_info(self):
        s = self.sample
        self.info.set(
            f"Displaying seed {s['seed']}  |  X {s['center_x']}, Z {s['center_z']}  |  {s['span']} x {s['span']} blocks  |  samples every {s['step']} blocks"
        )

    def start_drag(self, event):
        self.drag = (event.x, event.y)

    def orbit(self, event):
        oldx, oldy = getattr(self, "drag", (event.x, event.y))
        self.renderer.yaw += (event.x - oldx) * 0.008
        self.renderer.pitch = max(
            -0.8, min(1.56, self.renderer.pitch + (event.y - oldy) * 0.006)
        )
        self.drag = (event.x, event.y)
        self.request_render()

    def pan(self, event):
        oldx, oldy = getattr(self, "drag", (event.x, event.y))
        self.renderer.pan_x += event.x - oldx
        self.renderer.pan_y += event.y - oldy
        self.drag = (event.x, event.y)
        self.request_render()

    def zoom(self, event, direction=None):
        direction = (
            direction if direction is not None else (1 if event.delta > 0 else -1)
        )
        self.renderer.zoom = max(
            0.2, min(10, self.renderer.zoom * (1.15 if direction > 0 else 1 / 1.15))
        )
        self.request_render()

    def reset(self):
        self.renderer.reset()
        self.exaggeration.set(1)
        self.request_render()

    def top_view(self):
        self.renderer.pitch = 1.56
        self.renderer.yaw = 0
        self.request_render()

    def palette(self):
        design = self.app.gather_design()
        colors = design["colors"]
        result = {
            "grass": rgb(colors["grass_color"]),
            "water": rgb(colors["water_color"]),
            "tree1_leaves": rgb(colors["foliage_color"]),
            "tree2_leaves": rgb(colors["foliage_color"]),
            "tree1_count": design["tree1_count"],
            "tree2_count": design["tree2_count"],
            "deep_y": design["deep_y"],
        }
        if self.app.texture_dir.get():
            for role in (
                "grass_top",
                "dirt",
                "stone",
                "deepstone",
                "tree1_leaves",
                "tree2_leaves",
                "tree1_log",
                "tree2_log",
            ):
                image = texture_image(design, role, preview=True)
                if is_tinted(design, role):
                    image = self.app.apply_color(
                        image,
                        colors[
                            (
                                "foliage_color"
                                if role.endswith("_leaves")
                                else "grass_color"
                            )
                        ],
                    )
                visible = [
                    pixel[:3]
                    for pixel in image.convert("RGBA").getdata()
                    if pixel[3] > 100
                ]
                if visible:
                    result["grass" if role == "grass_top" else role] = tuple(
                        round(sum(p[i] for p in visible) / len(visible))
                        for i in range(3)
                    )
                if role == "grass_top":
                    result["grass_pixels"] = list(
                        image.convert("RGB")
                        .resize((16, 16), Image.Resampling.NEAREST)
                        .getdata()
                    )
        return result

    def request_render(self, *args):
        if self.pending is None and self.window.winfo_exists():
            self.pending = self.window.after(35, self.render)

    def render(self):
        self.pending = None
        try:
            palette = self.palette()
            self.renderer.vertical = 1
            mode = self.mode.get()
            self.renderer.cut = 0.5 if mode == "Half cutaway" else 1
            self.renderer.y_limit = (
                int(self.slice_y.get()) + 1 if mode == "Horizontal slice" else 320
            )
            self.renderer.floor_y = (
                int(self.slice_y.get())
                if mode == "Horizontal slice"
                else (
                    -64
                    if mode == "Half cutaway"
                    else max(-64, self.sample["min_height"] - 20)
                )
            )
            self.last_image = self.renderer.render(
                self.sample,
                (self.canvas.winfo_width(), self.canvas.winfo_height()),
                palette,
                self.water.get(),
                self.trees.get(),
                self.wire.get(),
            )
            self.photo = ImageTk.PhotoImage(self.last_image, master=self.window)
            self.canvas.delete("terrain")
            self.canvas.create_image(
                0, 0, image=self.photo, anchor="nw", tags="terrain"
            )
        except (ValueError, OSError, KeyError) as error:
            self.status.set(
                f"Finish the palette/settings to update the terrain colors: {error}"
            )

    def generate(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            config = self.get_config()
            request = SampleRequest(
                minecraft_seed(self.seed.get()),
                int(self.x.get()),
                int(self.z.get()),
                int(self.span.get()),
                int(self.detail.get()),
            ).validate()
        except ValueError as error:
            messagebox.showerror("Terrain settings", str(error), parent=self.window)
            return
        self.cancel = threading.Event()
        self.generate_button.config(state="disabled")
        self.cancel_button.config(state="normal")
        self.progress["value"] = 0
        self.status.set(
            "Starting Minecraft 26.3 terrain generation. The displayed sample stays available while this runs."
        )
        folder = (
            Path(os.environ.get("LOCALAPPDATA", Path.home()))
            / "BiomeConfiguratorFabric/terrain-samples"
        )

        def work():
            try:
                data = sample_terrain(
                    request,
                    folder,
                    lambda row, total: self.events.put(("progress", (row, total))),
                    self.cancel,
                    worldgen=config,
                    volume=True,
                )
                self.events.put(("done", data))
            except SampleCancelled:
                self.events.put(("cancelled", None))
            except Exception as error:
                self.events.put(("error", str(error)))

        self.worker = threading.Thread(target=work, daemon=False)
        self.generating_config = config
        self.worker.start()

    def poll(self):
        while True:
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "progress":
                self.progress["value"] = 100 * value[0] / value[1]
                self.status.set(
                    f"Sampling Minecraft terrain: row {value[0]} of {value[1]}..."
                )
            else:
                self.generate_button.config(state="normal")
                self.cancel_button.config(state="disabled")
                if kind == "done":
                    self.sample = value
                    self.update_sample_info()
                    self.progress["value"] = 100
                    try:
                        stale = self.sample.get("worldgen") != self.get_config()
                    except ValueError:
                        stale = True
                    self.status.set(
                        "Sample ready. Newer edits are pending; regenerate to compare."
                        if stale
                        else "Sample ready. Export uses this noise graph. Check final surface materials and decorations in Minecraft."
                    )
                    self.request_render()
                elif kind == "cancelled":
                    self.status.set(
                        "Sampling cancelled. The previous sample is still displayed."
                    )
                else:
                    self.status.set(
                        "Sampling could not finish. The previous sample is still displayed."
                    )
                    messagebox.showerror("Terrain sampler", value, parent=self.window)
        self.poll_id = self.window.after(100, self.poll)

    def save_image(self):
        path = filedialog.asksaveasfilename(
            parent=self.window,
            title="Save terrain preview image",
            defaultextension=".png",
            filetypes=[("PNG image", "*.png")],
        )
        if path and hasattr(self, "last_image"):
            self.last_image.save(path)

    def close(self):
        self.cancel.set()
        try:
            self.app.worldgen_config = self.get_config()
        except ValueError:
            pass
        if self.auto_id:
            self.window.after_cancel(self.auto_id)
        for variable, token in self.traces:
            variable.trace_remove("write", token)
        if self.pending:
            self.window.after_cancel(self.pending)
        if self.poll_id:
            self.window.after_cancel(self.poll_id)
        self.window.destroy()
        self.app.terrain_window = None
