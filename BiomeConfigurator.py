# Modified 2026-10-23: extract a scene drawing hook for the Fabric edition.
import tkinter as tk
from tkinter import ttk, colorchooser, filedialog, messagebox, simpledialog
import json
import os
import random
import shutil
import traceback

try:
    from PIL import Image, ImageTk, ImageChops
    HAS_PILLOW = True
except ImportError as e:
    HAS_PILLOW = False
    PILLOW_ERROR = str(e)

class BiomeConfiguratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Biome Configurator V1.0")
        self.root.geometry("800x900")

        # --- PRESET DICTIONARY ---
        # Starting with a couple of Vanilla presets as per the blueprint
        self.presets = {
            "Plains": {
                "sky_color": "#78A7FF",
                "fog_color": "#C0D8FF",
                "water_color": "#3F76E4",
                "water_fog_color": "#050533",
                "grass_color": "#91BD59",
                "foliage_color": "#77AB2F",
                "grass_color_modifier": "none",
                "has_precipitation": True,
                "temperature": 0.8,
                "downfall": 0.4,
                "mobs": [
                    {
                        "type": "minecraft:pig",
                        "category": "creature",
                        "weight": 10,
                        "minCount": 4,
                        "maxCount": 4,
                        "energy_budget": 0.12,
                        "charge": 1.0
                    }
                ],
                "ambient_particle": "none",
                "particle_probability": 0.0,
                "ambient_loop": "none",
                "ambient_mood": "none",
                "ambient_additions": "none"
            },
            "Soul Sand Valley": {
                "sky_color": "#110B0B",
                "fog_color": "#1B3B3F",
                "water_color": "#3F76E4",
                "water_fog_color": "#050533",
                "grass_color": "#000000", # N/A for this biome but required for schema
                "foliage_color": "#000000",
                "grass_color_modifier": "none",
                "has_precipitation": False,
                "temperature": 2.0,
                "downfall": 0.0,
                "mobs": [
                    {
                        "type": "minecraft:skeleton",
                        "category": "monster",
                        "weight": 20,
                        "minCount": 4,
                        "maxCount": 4,
                        "energy_budget": 0.12,
                        "charge": 1.0
                    }
                ],
                "ambient_particle": "minecraft:ash",
                "particle_probability": 0.025,
                "ambient_loop": "minecraft:ambient.soul_sand_valley.loop",
                "ambient_mood": "minecraft:ambient.soul_sand_valley.mood",
                "ambient_additions": "minecraft:ambient.soul_sand_valley.additions"
            },
            "Desert": {
                "sky_color": "#78A7FF",
                "fog_color": "#C0D8FF",
                "water_color": "#3F76E4",
                "water_fog_color": "#050533",
                "grass_color": "#BFB755",
                "foliage_color": "#AEA42A",
                "grass_color_modifier": "none",
                "has_precipitation": False,
                "temperature": 2.0,
                "downfall": 0.0,
                "mobs": [
                    {
                        "type": "minecraft:rabbit",
                        "category": "creature",
                        "weight": 4,
                        "minCount": 2,
                        "maxCount": 3,
                        "energy_budget": 0.12,
                        "charge": 1.0
                    },
                    {
                        "type": "minecraft:husk",
                        "category": "monster",
                        "weight": 80,
                        "minCount": 4,
                        "maxCount": 4,
                        "energy_budget": 0.12,
                        "charge": 1.0
                    }
                ],
                "ambient_particle": "none",
                "particle_probability": 0.0,
                "ambient_loop": "none",
                "ambient_mood": "none",
                "ambient_additions": "none"
            },
            "Basalt Deltas": {
                "sky_color": "#110B0B",
                "fog_color": "#68686B",
                "water_color": "#3F76E4",
                "water_fog_color": "#050533",
                "grass_color": "#000000",
                "foliage_color": "#000000",
                "grass_color_modifier": "none",
                "has_precipitation": False,
                "temperature": 2.0,
                "downfall": 0.0,
                "mobs": [
                    {
                        "type": "minecraft:magma_cube",
                        "category": "monster",
                        "weight": 100,
                        "minCount": 2,
                        "maxCount": 5,
                        "energy_budget": 0.12,
                        "charge": 1.0
                    },
                    {
                        "type": "minecraft:ghast",
                        "category": "monster",
                        "weight": 40,
                        "minCount": 1,
                        "maxCount": 1,
                        "energy_budget": 0.12,
                        "charge": 1.0
                    }
                ],
                "ambient_particle": "minecraft:white_ash",
                "particle_probability": 0.118,
                "ambient_loop": "minecraft:ambient.basalt_deltas.loop",
                "ambient_mood": "minecraft:ambient.basalt_deltas.mood",
                "ambient_additions": "minecraft:ambient.basalt_deltas.additions"
            },
            "Crimson Forest": {
                "sky_color": "#110B0B",
                "fog_color": "#330303",
                "water_color": "#3F76E4",
                "water_fog_color": "#050533",
                "grass_color": "#000000",
                "foliage_color": "#000000",
                "grass_color_modifier": "none",
                "has_precipitation": False,
                "temperature": 2.0,
                "downfall": 0.0,
                "mobs": [
                    {
                        "type": "minecraft:zombified_piglin",
                        "category": "monster",
                        "weight": 1,
                        "minCount": 2,
                        "maxCount": 4,
                        "energy_budget": 0.12,
                        "charge": 1.0
                    },
                    {
                        "type": "minecraft:piglin",
                        "category": "monster",
                        "weight": 8,
                        "minCount": 4,
                        "maxCount": 4,
                        "energy_budget": 0.12,
                        "charge": 1.0
                    }
                ],
                "ambient_particle": "minecraft:crimson_spore",
                "particle_probability": 0.025,
                "ambient_loop": "minecraft:ambient.crimson_forest.loop",
                "ambient_mood": "minecraft:ambient.crimson_forest.mood",
                "ambient_additions": "minecraft:ambient.crimson_forest.additions"
            }
        }

        # --- UI VARIABLES ---
        self.colors = {
            "sky_color": tk.StringVar(),
            "fog_color": tk.StringVar(),
            "water_color": tk.StringVar(),
            "water_fog_color": tk.StringVar(),
            "grass_color": tk.StringVar(),
            "foliage_color": tk.StringVar()
        }
        self.grass_modifier = tk.StringVar(value="none")
        self.has_precipitation = tk.BooleanVar(value=True)
        self.temperature = tk.DoubleVar(value=0.5)
        self.downfall = tk.DoubleVar(value=0.5)
        
        self.temp_display = tk.StringVar(value=f"{self.temperature.get():.4f}")
        self.downfall_display = tk.StringVar(value=f"{self.downfall.get():.4f}")
        self.temperature.trace_add("write", lambda *args: self.temp_display.set(f"{self.temperature.get():.4f}"))
        self.downfall.trace_add("write", lambda *args: self.downfall_display.set(f"{self.downfall.get():.4f}"))
        
        self.snow_y_level = tk.StringVar(value="")
        self.temperature.trace_add("write", self.update_snow_level)
        self.has_precipitation.trace_add("write", self.update_snow_level)
        
        self.active_mobs = []
        self.mob_id = tk.StringVar(value="")
        
        self.mob_category_map = {
            "minecraft:allay": "creature", "minecraft:armadillo": "creature", "minecraft:axolotl": "underground_water_creature",
            "minecraft:bat": "ambient", "minecraft:bee": "creature", "minecraft:blaze": "monster", "minecraft:bogged": "monster",
            "minecraft:breeze": "monster", "minecraft:camel": "creature", "minecraft:cat": "creature", "minecraft:cave_spider": "monster",
            "minecraft:chicken": "creature", "minecraft:cod": "water_ambient", "minecraft:cow": "creature", "minecraft:creeper": "monster",
            "minecraft:dolphin": "water_creature", "minecraft:donkey": "creature", "minecraft:drowned": "monster",
            "minecraft:elder_guardian": "monster", "minecraft:ender_dragon": "monster", "minecraft:enderman": "monster",
            "minecraft:endermite": "monster", "minecraft:evoker": "monster", "minecraft:fox": "creature", "minecraft:frog": "creature",
            "minecraft:ghast": "monster", "minecraft:giant": "monster", "minecraft:glow_squid": "underground_water_creature",
            "minecraft:goat": "creature", "minecraft:guardian": "monster", "minecraft:hoglin": "monster", "minecraft:horse": "creature",
            "minecraft:husk": "monster", "minecraft:illusioner": "monster", "minecraft:iron_golem": "misc", "minecraft:llama": "creature",
            "minecraft:magma_cube": "monster", "minecraft:mooshroom": "creature", "minecraft:mule": "creature", "minecraft:ocelot": "creature",
            "minecraft:panda": "creature", "minecraft:parrot": "creature", "minecraft:phantom": "monster", "minecraft:pig": "creature",
            "minecraft:piglin": "monster", "minecraft:piglin_brute": "monster", "minecraft:pillager": "monster", "minecraft:polar_bear": "creature",
            "minecraft:pufferfish": "water_ambient", "minecraft:rabbit": "creature", "minecraft:ravager": "monster", "minecraft:salmon": "water_ambient",
            "minecraft:sheep": "creature", "minecraft:shulker": "monster", "minecraft:silverfish": "monster", "minecraft:skeleton": "monster",
            "minecraft:skeleton_horse": "creature", "minecraft:slime": "monster", "minecraft:sniffer": "creature", "minecraft:snow_golem": "misc",
            "minecraft:spider": "monster", "minecraft:squid": "water_creature", "minecraft:stray": "monster", "minecraft:strider": "creature",
            "minecraft:tadpole": "water_creature", "minecraft:trader_llama": "creature", "minecraft:tropical_fish": "water_ambient",
            "minecraft:turtle": "creature", "minecraft:vex": "monster", "minecraft:villager": "misc", "minecraft:vindicator": "monster",
            "minecraft:wandering_trader": "misc", "minecraft:warden": "monster", "minecraft:witch": "monster", "minecraft:wither": "monster",
            "minecraft:wither_skeleton": "monster", "minecraft:wolf": "creature", "minecraft:zoglin": "monster", "minecraft:zombie": "monster",
            "minecraft:zombie_horse": "creature", "minecraft:zombie_villager": "monster", "minecraft:zombified_piglin": "monster"
        }
        self.mob_id.trace_add("write", self.auto_select_category)
        
        self.mob_weight = tk.IntVar(value=10)
        self.mob_min_pack = tk.IntVar(value=4)
        self.mob_max_pack = tk.IntVar(value=4)
        self.energy_budget = tk.DoubleVar(value=0.12)
        self.charge = tk.DoubleVar(value=1.0)
        
        self.local_cap_display = tk.StringVar(value="")
        self.energy_budget.trace_add("write", self.update_local_cap)
        self.charge.trace_add("write", self.update_local_cap)
        self.update_local_cap()

        self.ambient_particle = tk.StringVar(value="none")
        self.particle_probability = tk.DoubleVar(value=0.0)
        self.particle_prob_display = tk.StringVar(value=f"{self.particle_probability.get():.4f}")
        self.particle_probability.trace_add("write", lambda *args: self.particle_prob_display.set(f"{self.particle_probability.get():.4f}"))
        self.ambient_loop = tk.StringVar(value="none")
        self.ambient_mood = tk.StringVar(value="none")
        self.ambient_additions = tk.StringVar(value="none")
        
        self.export_name = tk.StringVar(value="my_custom_biome")

        self.preset_dir = "presets"
        os.makedirs(self.preset_dir, exist_ok=True)
        self.load_local_presets()
        self.load_base_textures()
        self.generate_3d_scene()

        self.create_layout()
        
        # Load the first preset by default
        self.preset_combo.current(0)
        self.load_preset()
        
        # Initialize Phase 2 Canvas bindings and animation loop
        self.preview_canvas.bind("<Configure>", self.update_preview)
        self.animate()

    def generate_3d_scene(self):
        """Generates a hardcoded isometric 3D chunk representation."""
        self.scene_blocks = []
        # Build a stylized 7x7 island (X, Y, Z, type)
        for x in range(7):
            for z in range(7):
                if (x==0 and z==0) or (x==6 and z==6) or (x==0 and z==6) or (x==6 and z==0):
                    continue # Cut corners to make it round
                if x >= 4 and z >= 4:
                    self.scene_blocks.append((x, 0, z, 'water'))
                else:
                    self.scene_blocks.append((x, 0, z, 'grass'))
        
        # Add an Oak Tree
        self.scene_blocks.extend([(2, 1, 2, 'wood'), (2, 2, 2, 'wood')])
        for lx in range(1, 4):
            for lz in range(1, 4):
                self.scene_blocks.append((lx, 3, lz, 'leaves'))
        self.scene_blocks.extend([(2, 4, 2, 'leaves'), (2, 4, 1, 'leaves'), (1, 4, 2, 'leaves'), (3, 4, 2, 'leaves')])

        # Painter's Algorithm: Sort blocks back-to-front for proper overlapping
        self.scene_blocks.sort(key=lambda b: (b[0], b[2], b[1]))

    def load_base_textures(self):
        """Loads 16x16 textures from folder, or generates synthetic grayscale noise if missing."""
        tex_dir = "textures"
        os.makedirs(tex_dir, exist_ok=True)
        
        def get_or_create(filename, brightness, noise_range=15):
            path = os.path.join(tex_dir, filename)
            if os.path.exists(path):
                return Image.open(path).convert("RGBA").resize((16, 16))
            
            # Procedural fallback generator
            img = Image.new("RGBA", (16, 16))
            px = img.load()
            for y in range(16):
                for x in range(16):
                    v = max(0, min(255, brightness + random.randint(-noise_range, noise_range)))
                    # Add some transparency to leaves
                    a = 255 if "leaves" not in filename else (255 if random.random() > 0.3 else 0)
                    px[x, y] = (v, v, v, a)
            return img
            
        self.tex_grass_top = get_or_create("grass_block_top.png", 180)
        self.tex_dirt = get_or_create("dirt.png", 120)
        self.tex_water = get_or_create("water_still.png", 200, 5)
        self.tex_leaves = get_or_create("oak_leaves.png", 150)
        self.tex_wood_top = get_or_create("oak_log_top.png", 130)
        self.tex_wood_side = get_or_create("oak_log.png", 100)

    def apply_color(self, img, hex_color):
        """Multiplies a grayscale image by a biome hex color exactly like Minecraft."""
        color_img = Image.new("RGBA", img.size, hex_color)
        mask = img.split()[3] # Preserve transparency (for leaves)
        colored = ImageChops.multiply(img.convert("RGB"), color_img.convert("RGB"))
        colored.putalpha(mask)
        return colored

    def build_iso_block(self, top_img, left_img, right_img):
        """Warps three 16x16 textures into a perfect 33x33 isometric cube."""
        block = Image.new("RGBA", (33, 33), (0, 0, 0, 0))
        top_px = top_img.convert("RGBA").load()
        left_px = left_img.convert("RGBA").load()
        right_px = right_img.convert("RGBA").load()
        b_px = block.load()

        def shade(c, factor): return (int(c[0]*factor), int(c[1]*factor), int(c[2]*factor), c[3])

        # Right Face (Darkest)
        for y in range(16):
            for x in range(16):
                if right_px[x, y][3] == 0: continue
                c = shade(right_px[x, y], 0.6)
                ix, iy = 16 + x, 15 - x // 2 + y
                b_px[ix, iy], b_px[ix+1, iy] = c, c

        # Left Face (Medium)
        for y in range(16):
            for x in range(16):
                if left_px[x, y][3] == 0: continue
                c = shade(left_px[x, y], 0.8)
                ix, iy = x, 8 + x // 2 + y
                b_px[ix, iy], b_px[ix+1, iy] = c, c

        # Top Face (Brightest)
        for y in range(16):
            for x in range(16):
                if top_px[x, y][3] == 0: continue
                ix, iy = 15 + x - y, (x + y) // 2
                b_px[ix, iy], b_px[ix+1, iy] = top_px[x, y], top_px[x, y]

        return block

    def regenerate_textures(self):
        """Compiles and caches the active textures based on current color selections."""
        raw_grass = self.colors["grass_color"].get() or "#91BD59"
        raw_foliage = self.colors["foliage_color"].get() or "#77AB2F"
        water_color = self.colors["water_color"].get() or "#3F76E4"
        
        if self.grass_modifier.get() == "dark_forest":
            raw_grass = self.multiply_color_string(raw_grass, 0.6)
            raw_foliage = self.multiply_color_string(raw_foliage, 0.6)
            
        # Check for Snow!
        is_snowy = self.has_precipitation.get() and self.temperature.get() < 0.15
        if is_snowy: raw_grass = "#FFFFFF"

        # Apply Colors to Raw Textures
        grass_top = self.apply_color(self.tex_grass_top, raw_grass)
        dirt_face = self.apply_color(self.tex_dirt, "#FFFFFF")
        water_face = self.apply_color(self.tex_water, water_color)
        leaves_face = self.apply_color(self.tex_leaves, raw_foliage)
        wood_top = self.apply_color(self.tex_wood_top, "#FFFFFF")
        wood_side = self.apply_color(self.tex_wood_side, "#FFFFFF")
        
        # Composite the Grass Side overlay
        grass_side = dirt_face.copy()
        grass_side.paste(grass_top.crop((0,0,16,4)), (0,0))

        # Build and Cache Isometric Blocks
        img_grass = self.build_iso_block(grass_top, grass_side, grass_side)
        img_water = self.build_iso_block(water_face, water_face, water_face)
        img_leaves = self.build_iso_block(leaves_face, leaves_face, leaves_face)
        img_wood = self.build_iso_block(wood_top, wood_side, wood_side)

        self.cached_blocks = {
            'grass': ImageTk.PhotoImage(img_grass), 'water': ImageTk.PhotoImage(img_water),
            'leaves': ImageTk.PhotoImage(img_leaves), 'wood': ImageTk.PhotoImage(img_wood)
        }

    def create_layout(self):
        # --- TOP CONTROLS ---
        top_frame = ttk.Frame(self.root)
        top_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(top_frame, text="Template:").pack(side=tk.LEFT)
        self.preset_combo = ttk.Combobox(top_frame, values=list(self.presets.keys()), state="readonly")
        self.preset_combo.pack(side=tk.LEFT, padx=10)
        self.preset_combo.bind("<<ComboboxSelected>>", self.load_preset)
        
        ttk.Button(top_frame, text="Save Preset", command=self.save_custom_preset).pack(side=tk.LEFT, padx=5)

        # --- LIVE PREVIEW CANVAS (Phase 2 Placeholder) ---
        ttk.Label(self.root, text="Live Preview").pack(anchor=tk.W, padx=10)
        self.preview_canvas = tk.Canvas(self.root, height=300, bg="grey", highlightthickness=1, highlightbackground="black")
        self.preview_canvas.pack(fill=tk.X, padx=10, pady=(0, 15))

        # --- NOTEBOOK TABS ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.tab_atmosphere = ttk.Frame(self.notebook)
        self.tab_climate = ttk.Frame(self.notebook)
        self.tab_spawns = ttk.Frame(self.notebook)
        self.tab_ambience = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_atmosphere, text="Atmosphere")
        self.notebook.add(self.tab_climate, text="Climate")
        self.notebook.add(self.tab_spawns, text="Spawns & Caps")
        self.notebook.add(self.tab_ambience, text="Ambience")

        self.build_atmosphere_tab()
        self.build_climate_tab()
        self.build_spawns_tab()
        self.build_ambience_tab()

        # --- EXPORT CONTROLS ---
        export_frame = ttk.Frame(self.root)
        export_frame.pack(pady=10)
        ttk.Label(export_frame, text="Biome ID:").pack(side=tk.LEFT)
        ttk.Entry(export_frame, textvariable=self.export_name).pack(side=tk.LEFT, padx=5)
        ttk.Button(export_frame, text="Export Biome JSON", command=self.export_json).pack(side=tk.LEFT)
        ttk.Button(export_frame, text="Generate Datapack", command=self.generate_datapack).pack(side=tk.LEFT, padx=5)
        ttk.Button(export_frame, text="Clear Staging", command=self.clear_staging).pack(side=tk.LEFT)

    def build_atmosphere_tab(self):
        row = 0
        for name, var in self.colors.items():
            ttk.Label(self.tab_atmosphere, text=name.replace("_", " ").title() + ":").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
            
            # Entry to show hex code (using tk.Entry to support background color changes)
            entry = tk.Entry(self.tab_atmosphere, textvariable=var, width=10)
            entry.grid(row=row, column=1, padx=5, pady=5)
            
            # Trace to dynamically update background color
            var.trace_add("write", lambda *args, v=var, e=entry: self.update_entry_color(v, e))
            
            # Button to open color picker
            btn = ttk.Button(self.tab_atmosphere, text="Pick Color", command=lambda n=name, v=var: self.pick_color(n, v))
            btn.grid(row=row, column=2, padx=5, pady=5)
            
            row += 1

        ttk.Label(self.tab_atmosphere, text="Grass Modifier:").grid(row=row, column=0, padx=10, pady=5, sticky=tk.W)
        modifier_combo = ttk.Combobox(self.tab_atmosphere, textvariable=self.grass_modifier, values=["none", "swamp", "dark_forest"], state="readonly")
        modifier_combo.grid(row=row, column=1, columnspan=2, sticky=tk.W, padx=5, pady=5)
        modifier_combo.bind("<<ComboboxSelected>>", self.update_preview)

    def build_climate_tab(self):
        ttk.Checkbutton(self.tab_climate, text="Has Precipitation", variable=self.has_precipitation).grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)
        
        ttk.Label(self.tab_climate, text="Temperature (-1.0 to 2.0):").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Scale(self.tab_climate, from_=-1.0, to=2.0, variable=self.temperature, orient=tk.HORIZONTAL, length=200).grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(self.tab_climate, textvariable=self.temp_display).grid(row=1, column=2, padx=5)

        ttk.Label(self.tab_climate, text="Downfall (0.0 to 1.0):").grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Scale(self.tab_climate, from_=0.0, to=1.0, variable=self.downfall, orient=tk.HORIZONTAL, length=200).grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(self.tab_climate, textvariable=self.downfall_display).grid(row=2, column=2, padx=5)

    def build_spawns_tab(self):
        # Split into left and right frames
        left_frame = ttk.Frame(self.tab_spawns)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        right_frame = ttk.Frame(self.tab_spawns)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left Frame: Listbox
        ttk.Label(left_frame, text="Active Mobs:").pack(anchor=tk.W)
        self.mob_listbox = tk.Listbox(left_frame, width=35)
        self.mob_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        
        remove_btn = ttk.Button(left_frame, text="Remove Selected", command=self.remove_mob)
        remove_btn.pack(anchor=tk.W)
        
        # Right Frame: Input Fields
        self.mob_category = tk.StringVar(value="creature")
        
        row = 0
        ttk.Label(right_frame, text="Mob ID:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        common_mobs = [
            "minecraft:allay", "minecraft:armadillo", "minecraft:axolotl", "minecraft:bat", "minecraft:bee",
            "minecraft:blaze", "minecraft:bogged", "minecraft:breeze", "minecraft:camel", "minecraft:cat",
            "minecraft:cave_spider", "minecraft:chicken", "minecraft:cod", "minecraft:cow", "minecraft:creeper",
            "minecraft:dolphin", "minecraft:donkey", "minecraft:drowned", "minecraft:elder_guardian",
            "minecraft:ender_dragon", "minecraft:enderman", "minecraft:endermite", "minecraft:evoker",
            "minecraft:fox", "minecraft:frog", "minecraft:ghast", "minecraft:giant", "minecraft:glow_squid",
            "minecraft:goat", "minecraft:guardian", "minecraft:hoglin", "minecraft:horse", "minecraft:husk",
            "minecraft:illusioner", "minecraft:iron_golem", "minecraft:llama", "minecraft:magma_cube",
            "minecraft:mooshroom", "minecraft:mule", "minecraft:ocelot", "minecraft:panda", "minecraft:parrot",
            "minecraft:phantom", "minecraft:pig", "minecraft:piglin", "minecraft:piglin_brute", "minecraft:pillager",
            "minecraft:polar_bear", "minecraft:pufferfish", "minecraft:rabbit", "minecraft:ravager", "minecraft:salmon",
            "minecraft:sheep", "minecraft:shulker", "minecraft:silverfish", "minecraft:skeleton",
            "minecraft:skeleton_horse", "minecraft:slime", "minecraft:sniffer", "minecraft:snow_golem",
            "minecraft:spider", "minecraft:squid", "minecraft:stray", "minecraft:strider", "minecraft:tadpole",
            "minecraft:trader_llama", "minecraft:tropical_fish", "minecraft:turtle", "minecraft:vex",
            "minecraft:villager", "minecraft:vindicator", "minecraft:wandering_trader", "minecraft:warden",
            "minecraft:witch", "minecraft:wither", "minecraft:wither_skeleton", "minecraft:wolf", "minecraft:zoglin",
            "minecraft:zombie", "minecraft:zombie_horse", "minecraft:zombie_villager", "minecraft:zombified_piglin"
        ]
        ttk.Combobox(right_frame, textvariable=self.mob_id, values=common_mobs).grid(row=row, column=1, padx=5, pady=5, sticky=tk.W)
        
        row += 1
        ttk.Label(right_frame, text="Category:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        categories = ["monster", "creature", "ambient", "water_creature", "water_ambient", "underground_water_creature", "misc"]
        ttk.Combobox(right_frame, textvariable=self.mob_category, values=categories, state="readonly").grid(row=row, column=1, padx=5, pady=5, sticky=tk.W)

        row += 1
        ttk.Label(right_frame, text="Spawn Weight:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(right_frame, textvariable=self.mob_weight, width=10).grid(row=row, column=1, padx=5, pady=5, sticky=tk.W)

        row += 1
        ttk.Label(right_frame, text="Min Pack Size:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(right_frame, textvariable=self.mob_min_pack, width=10).grid(row=row, column=1, padx=5, pady=5, sticky=tk.W)

        row += 1
        ttk.Label(right_frame, text="Max Pack Size:").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(right_frame, textvariable=self.mob_max_pack, width=10).grid(row=row, column=1, padx=5, pady=5, sticky=tk.W)

        row += 1
        ttk.Label(right_frame, text="Area Budget (Energy):").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(right_frame, textvariable=self.energy_budget, width=10).grid(row=row, column=1, padx=5, pady=5, sticky=tk.W)

        row += 1
        ttk.Label(right_frame, text="Mob Cost (Charge):").grid(row=row, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(right_frame, textvariable=self.charge, width=10).grid(row=row, column=1, padx=5, pady=5, sticky=tk.W)

        row += 1
        ttk.Label(right_frame, textvariable=self.local_cap_display, font=("", 9, "italic")).grid(row=row, column=0, columnspan=2, padx=5, pady=(0, 5), sticky=tk.W)

        row += 1
        add_btn = ttk.Button(right_frame, text="Add Mob to List", command=self.add_mob)
        add_btn.grid(row=row, column=0, columnspan=2, pady=10)

    def add_mob(self):
        mob = self.mob_id.get().strip()
        if not mob: return
        
        try:
            mob_data = {
                "type": mob,
                "category": self.mob_category.get(),
                "weight": self.mob_weight.get(),
                "minCount": self.mob_min_pack.get(),
                "maxCount": self.mob_max_pack.get(),
                "energy_budget": self.energy_budget.get(),
                "charge": self.charge.get()
            }
            self.active_mobs.append(mob_data)
            self.update_mob_listbox()
        except tk.TclError:
            pass # Ignore invalid int/float form entries
            
    def remove_mob(self):
        selection = self.mob_listbox.curselection()
        if selection:
            del self.active_mobs[selection[0]]
            self.update_mob_listbox()
            
    def update_mob_listbox(self):
        self.mob_listbox.delete(0, tk.END)
        for mob in self.active_mobs:
            self.mob_listbox.insert(tk.END, f"{mob['type']} ({mob['category']}) - W:{mob['weight']}")

    def build_ambience_tab(self):
        ttk.Label(self.tab_ambience, text="Ambient Particle:").grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        particles = ["none", "minecraft:ash", "minecraft:white_ash", "minecraft:crimson_spore", "minecraft:warped_spore", "minecraft:falling_spore_blossom"]
        ttk.Combobox(self.tab_ambience, textvariable=self.ambient_particle, values=particles).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(self.tab_ambience, text="Particle Probability:").grid(row=1, column=0, padx=10, pady=5, sticky=tk.W)
        ttk.Scale(self.tab_ambience, from_=0.0, to=1.0, variable=self.particle_probability, orient=tk.HORIZONTAL, length=150).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Label(self.tab_ambience, textvariable=self.particle_prob_display).grid(row=1, column=2, padx=5)

        ttk.Label(self.tab_ambience, text="Ambient Loop:").grid(row=2, column=0, padx=10, pady=5, sticky=tk.W)
        loops = [
            "none",
            "minecraft:ambient.basalt_deltas.loop",
            "minecraft:ambient.crimson_forest.loop",
            "minecraft:ambient.dripstone_caves.loop",
            "minecraft:ambient.lush_caves.loop",
            "minecraft:ambient.nether_wastes.loop",
            "minecraft:ambient.soul_sand_valley.loop",
            "minecraft:ambient.underwater.loop",
            "minecraft:ambient.warped_forest.loop"
        ]
        ttk.Combobox(self.tab_ambience, textvariable=self.ambient_loop, values=loops, width=37).grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)

        ttk.Label(self.tab_ambience, text="Ambient Mood:").grid(row=3, column=0, padx=10, pady=5, sticky=tk.W)
        moods = [
            "none",
            "minecraft:ambient.basalt_deltas.mood",
            "minecraft:ambient.cave",
            "minecraft:ambient.crimson_forest.mood",
            "minecraft:ambient.dripstone_caves.mood",
            "minecraft:ambient.lush_caves.mood",
            "minecraft:ambient.nether_wastes.mood",
            "minecraft:ambient.soul_sand_valley.mood",
            "minecraft:ambient.warped_forest.mood"
        ]
        ttk.Combobox(self.tab_ambience, textvariable=self.ambient_mood, values=moods, width=37).grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)

        ttk.Label(self.tab_ambience, text="Ambient Additions:").grid(row=4, column=0, padx=10, pady=5, sticky=tk.W)
        additions = [
            "none",
            "minecraft:ambient.basalt_deltas.additions",
            "minecraft:ambient.crimson_forest.additions",
            "minecraft:ambient.dripstone_caves.additions",
            "minecraft:ambient.lush_caves.additions",
            "minecraft:ambient.nether_wastes.additions",
            "minecraft:ambient.soul_sand_valley.additions",
            "minecraft:ambient.warped_forest.additions"
        ]
        ttk.Combobox(self.tab_ambience, textvariable=self.ambient_additions, values=additions, width=37).grid(row=4, column=1, columnspan=2, padx=5, pady=5, sticky=tk.W)

    def pick_color(self, name, var):
        current_color = var.get() or "#FFFFFF"
        try:
            color = colorchooser.askcolor(color=current_color, title=f"Choose {name}")[1]
        except tk.TclError:
            # Fallback if the user typed an invalid hex code manually
            color = colorchooser.askcolor(title=f"Choose {name}")[1]
            
        if color:
            var.set(color)
            self.update_preview()

    def update_entry_color(self, var, entry):
        """Dynamically changes the text entry background color and adjusts text contrast."""
        hex_color = var.get()
        try:
            if len(hex_color) == 7 and hex_color.startswith("#"):
                entry.config(bg=hex_color)
                # Calculate brightness (YIQ formula) to determine if text should be black or white
                r, g, b = int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16)
                brightness = (r * 299 + g * 587 + b * 114) / 1000
                entry.config(fg="white" if brightness < 128 else "black")
            else:
                entry.config(bg="white", fg="black")
        except ValueError:
            entry.config(bg="white", fg="black")

    def load_preset(self, event=None):
        selection = self.preset_combo.get()
        if selection in self.presets:
            preset = self.presets[selection]
            
            # Update Colors
            for key, val in self.colors.items():
                val.set(preset.get(key, "#FFFFFF"))
            
            # Update Climate & Modifiers
            self.grass_modifier.set(preset.get("grass_color_modifier", "none"))
            self.has_precipitation.set(preset.get("has_precipitation", True))
            self.temperature.set(preset.get("temperature", 0.5))
            self.downfall.set(preset.get("downfall", 0.5))
            
            # Update Spawns
            self.active_mobs = [dict(mob) for mob in preset.get("mobs", [])]
            if hasattr(self, 'mob_listbox'):
                self.update_mob_listbox()
            
            # Update Ambience
            self.ambient_particle.set(preset.get("ambient_particle", "none"))
            self.particle_probability.set(preset.get("particle_probability", 0.0))
            self.ambient_loop.set(preset.get("ambient_loop", "none"))
            self.ambient_mood.set(preset.get("ambient_mood", "none"))
            self.ambient_additions.set(preset.get("ambient_additions", "none"))
            
            print(f"Loaded Preset: {selection}")
            self.update_preview()

    def load_local_presets(self):
        for filename in os.listdir(self.preset_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.preset_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        preset = json.load(f)
                    preset_name = filename[:-5]
                    self.presets[preset_name] = preset
                except Exception as e:
                    print(f"Failed to load preset {filename}: {e}")

    def save_custom_preset(self):
        preset_name = self.export_name.get().strip() or "custom_preset"
        file_path = os.path.join(self.preset_dir, f"{preset_name}.json")
            
        preset_data = {
            "sky_color": self.colors["sky_color"].get(),
            "fog_color": self.colors["fog_color"].get(),
            "water_color": self.colors["water_color"].get(),
            "water_fog_color": self.colors["water_fog_color"].get(),
            "grass_color": self.colors["grass_color"].get(),
            "foliage_color": self.colors["foliage_color"].get(),
            "grass_color_modifier": self.grass_modifier.get(),
            "has_precipitation": self.has_precipitation.get(),
            "temperature": self.temperature.get(),
            "downfall": self.downfall.get(),
            "mobs": self.active_mobs,
            "ambient_particle": self.ambient_particle.get(),
            "particle_probability": self.particle_probability.get(),
            "ambient_loop": self.ambient_loop.get(),
            "ambient_mood": self.ambient_mood.get(),
            "ambient_additions": self.ambient_additions.get()
        }
        
        with open(file_path, 'w') as f:
            json.dump(preset_data, f, indent=4)
            
        self.presets[preset_name] = preset_data
        self.preset_combo['values'] = list(self.presets.keys())
        self.preset_combo.set(preset_name)
        
        print(f"Successfully saved preset to {file_path}")

    def hex_to_int(self, hex_color):
        """Converts #RRGGBB string to Minecraft's expected decimal integer."""
        try:
            return int(hex_color.lstrip('#'), 16)
        except ValueError:
            return 0

    def auto_select_category(self, *args):
        mob = self.mob_id.get().strip()
        if mob in self.mob_category_map:
            self.mob_category.set(self.mob_category_map[mob])

    def update_local_cap(self, *args):
        """Calculates and displays the localized mob cap based on energy budget and charge."""
        try:
            budget = self.energy_budget.get()
            charge = self.charge.get()
            if charge > 0:
                cap = budget / charge
                self.local_cap_display.set(f"↳ Caps this mob at ~{cap:.2f} per local area")
            else:
                self.local_cap_display.set("↳ Infinite spawns (Warning: Charge is 0)")
        except tk.TclError:
            self.local_cap_display.set("↳ Awaiting valid numbers...")

    def update_snow_level(self, *args):
        """Calculates and updates the Y-level at which snow replaces rain based on temperature."""
        if not self.has_precipitation.get():
            self.snow_y_level.set("No precipitation")
        else:
            temp = self.temperature.get()
            if temp < 0.15:
                self.snow_y_level.set("Snow at all Y-levels")
            else:
                # Modern Minecraft drops temp by 1/800 per block above Y=80
                y_level = int(80 + (temp - 0.15) * 800)
                self.snow_y_level.set(f"Snow at Y={y_level} (±8)")
                    
        if hasattr(self, 'preview_canvas'):
            self.preview_canvas.itemconfig("snow_text", text=self.snow_y_level.get())

    def export_json(self):
        biome_id = self.export_name.get().strip() or "custom_biome"
        
        # 1. Compile Effects
        effects = {
            "sky_color": self.hex_to_int(self.colors["sky_color"].get()),
            "fog_color": self.hex_to_int(self.colors["fog_color"].get()),
            "water_color": self.hex_to_int(self.colors["water_color"].get()),
            "water_fog_color": self.hex_to_int(self.colors["water_fog_color"].get()),
            "grass_color": self.hex_to_int(self.colors["grass_color"].get()),
            "foliage_color": self.hex_to_int(self.colors["foliage_color"].get())
        }
        
        if self.grass_modifier.get() != "none":
            effects["grass_color_modifier"] = self.grass_modifier.get()
            
        if self.ambient_particle.get() != "none":
            effects["particle"] = {
                "options": {"type": self.ambient_particle.get()},
                "probability": round(self.particle_probability.get(), 4)
            }
        if self.ambient_loop.get() != "none":
            effects["ambient_sound"] = self.ambient_loop.get()
        if self.ambient_mood.get() != "none":
            effects["mood_sound"] = {"sound": self.ambient_mood.get(), "tick_delay": 6000, "block_search_extent": 8, "offset": 2.0}
        if self.ambient_additions.get() != "none":
            effects["additions_sound"] = {"sound": self.ambient_additions.get(), "tick_chance": 0.0111}

        # 2. Compile Spawns
        spawners = {}
        spawn_costs = {}
        
        for mob in getattr(self, 'active_mobs', []):
            cat = mob.get("category", "creature")
            if cat not in spawners:
                spawners[cat] = []

            spawners[cat].append({
                "type": mob["type"],
                "weight": mob["weight"],
                "minCount": mob["minCount"],
                "maxCount": mob["maxCount"]
            })
            spawn_costs[mob["type"]] = {
                "energy_budget": mob["energy_budget"],
                "charge": mob["charge"]
            }

        # 3. Assemble Core JSON Structure
        biome_data = {
            "has_precipitation": self.has_precipitation.get(),
            "temperature": round(self.temperature.get(), 4),
            "downfall": round(self.downfall.get(), 4),
            "creature_spawn_probability": 0.1,
            "effects": effects,
            "carvers": [],
            "features": [[], [], [], [], [], [], [], [], [], [], []]
        }
        
        if spawners:
            biome_data["spawners"] = spawners
        if spawn_costs:
            biome_data["spawn_costs"] = spawn_costs

        # 4. Export File
        export_dir = os.path.join("output", "data", "custom", "worldgen", "biome")
        os.makedirs(export_dir, exist_ok=True)
        file_path = os.path.join(export_dir, f"{biome_id}.json")
        
        with open(file_path, 'w') as f:
            json.dump(biome_data, f, indent=2)
            
        print(f"Successfully exported biome to {file_path}")

    def generate_datapack(self):
        # Ensure the default output/datapacks folder exists
        default_out = os.path.join("output", "datapacks")
        os.makedirs(default_out, exist_ok=True)
        
        # Ask for Datapack Name first to bypass OS folder navigation quirks
        pack_name = simpledialog.askstring(
            "Datapack Name",
            "Enter the name for your Datapack:",
            initialvalue="Custom Biomes",
            parent=self.root
        )
        if not pack_name:
            return
        
        # Prompt user for export location
        target_dir = filedialog.askdirectory(
            initialdir=os.path.abspath(default_out),
            title=f"Select Location to drop '{pack_name}'"
        )
        if not target_dir:
            return
            
        pack_dir = os.path.join(target_dir, pack_name)
        os.makedirs(pack_dir, exist_ok=True)
        
        # Create pack.mcmeta
        mcmeta = {
            "pack": {
                "pack_format": 26,
                "description": "Custom Biomes for WorldPainter"
            }
        }
        with open(os.path.join(pack_dir, "pack.mcmeta"), "w") as f:
            json.dump(mcmeta, f, indent=2)
            
        # Copy the staged /data folder into the datapack
        staging_data = os.path.join("output", "data")
        if os.path.exists(staging_data):
            dest_data = os.path.join(pack_dir, "data")
            shutil.copytree(staging_data, dest_data, dirs_exist_ok=True)
            messagebox.showinfo("Success", f"Datapack successfully generated at:\n{pack_dir}")
        else:
            messagebox.showwarning("No Data", "No biomes have been exported yet!\nPlease click 'Export Biome JSON' on at least one biome before generating a datapack.")

    def clear_staging(self):
        staging_dir = os.path.join("output", "data")
        if os.path.exists(staging_dir):
            try:
                shutil.rmtree(staging_dir)
                messagebox.showinfo("Success", "Staging folder cleared!\nYou can now start fresh without old broken biomes sneaking into your datapacks.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to clear staging folder:\n{e}")
        else:
            messagebox.showinfo("Info", "Staging folder is already empty.")

    # --- PHASE 2: LIVE PREVIEW & ANIMATION ENGINE ---
    def update_preview(self, event=None):
        self.preview_canvas.delete("static")
        self.preview_canvas.delete("overlay")
        width = self.preview_canvas.winfo_width()
        height = self.preview_canvas.winfo_height()
        if width <= 1 or height <= 1:
            width, height = 800, 300
            
        horizon = height // 2
        
        # 1. Sky Background (Top Half)
        sky_color = self.colors["sky_color"].get() or "#78A7FF"
        self.preview_canvas.create_rectangle(0, 0, width, horizon // 2, fill=sky_color, outline="", tags="static")
        
        # 2. Fog Gradient Overlay (Blending sky to fog at the horizon)
        fog_color = self.colors["fog_color"].get() or "#C0D8FF"
        gradient_steps = 15
        grad_start = horizon // 2
        grad_height = horizon - grad_start
        for i in range(gradient_steps):
            fraction = i / (gradient_steps - 1)
            color = self.interpolate_color(sky_color, fog_color, fraction)
            y1 = grad_start + (grad_height / gradient_steps) * i
            y2 = grad_start + (grad_height / gradient_steps) * (i + 1)
            self.preview_canvas.create_rectangle(0, y1, width, y2, fill=color, outline="", tags="static")
        
        # 3. Draw Textured 3D Isometric Terrain
        current_colors = (
            self.colors["grass_color"].get(), self.colors["foliage_color"].get(),
            self.colors["water_color"].get(), self.grass_modifier.get(),
            self.has_precipitation.get(), self.temperature.get()
        )
        # Only re-calculate the intensive texture math if a slider or color actually changed
        if not hasattr(self, 'last_colors') or self.last_colors != current_colors:
            self.regenerate_textures()
            self.last_colors = current_colors
        
        # Reverted Zoom: Original Matrix Proportions
        origin_x, origin_y = width // 2, horizon - 10
        tile_w, tile_h, block_h = 16, 8, 16 
        
        self.draw_scene(origin_x, origin_y, tile_w, tile_h, block_h)
        
        # Ensure new static background renders behind any active weather
        self.preview_canvas.tag_lower("static")
        
        # 5. Snow Level Overlay
        self.preview_canvas.create_text(width - 10, 10, anchor=tk.NE, text=self.snow_y_level.get(), fill="white", font=("Arial", 10, "bold"), tags=("overlay", "snow_text"))

    def draw_scene(self, origin_x, origin_y, tile_w, tile_h, block_h):
        for x, y, z, block_type in self.scene_blocks:
            sx = origin_x + (x - z) * tile_w
            sy = origin_y + (x + z) * tile_h - (y * block_h)
            if hasattr(self, 'cached_blocks') and block_type in self.cached_blocks:
                self.preview_canvas.create_image(sx, sy - tile_h, image=self.cached_blocks[block_type], anchor=tk.N, tags="static")

    def multiply_color_string(self, hex_color, factor):
        """Utility to multiply hex strings for flat colors."""
        try:
            hex_color = hex_color.lstrip('#')
            r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            r, g, b = int(r * factor), int(g * factor), int(b * factor)
            r, g, b = min(255, max(0, r)), min(255, max(0, g)), min(255, max(0, b))
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return hex_color
            
    def interpolate_color(self, hex1, hex2, fraction):
        """Interpolates between two hex colors for gradient effects."""
        try:
            h1 = hex1.lstrip('#')
            h2 = hex2.lstrip('#')
            if len(h1) != 6 or len(h2) != 6:
                return hex1 # Fallback for invalid hex strings
                
            r1, g1, b1 = tuple(int(h1[i:i+2], 16) for i in (0, 2, 4))
            r2, g2, b2 = tuple(int(h2[i:i+2], 16) for i in (0, 2, 4))
            
            r = int(r1 + (r2 - r1) * fraction)
            g = int(g1 + (g2 - g1) * fraction)
            b = int(b1 + (b2 - b1) * fraction)
            return f"#{min(255, max(0, r)):02x}{min(255, max(0, g)):02x}{min(255, max(0, b)):02x}"
        except:
            return "#FFFFFF"

    def animate(self):
        width = self.preview_canvas.winfo_width()
        height = self.preview_canvas.winfo_height()
        
        if width > 1 and height > 1:
            # Move existing weather
            self.preview_canvas.move("rain", 0, 15)
            self.preview_canvas.move("snow", random.randint(-2, 2), 5)
            self.preview_canvas.move("particle_up", random.randint(-2, 2), -2)
            self.preview_canvas.move("particle_down", random.randint(-2, 2), 2)
            
            # Optimized Cleanup: Use overlapping boxes to cull off-screen items natively
            # Check bottom edge (falling rain/snow and falling spores)
            for item in self.preview_canvas.find_overlapping(-50, height + 5, width + 50, height + 100):
                tags = self.preview_canvas.gettags(item)
                if "weather" in tags or "ambient_particle" in tags:
                    self.preview_canvas.delete(item)
                    
            # Check top edge (floating ash/spores)
            for item in self.preview_canvas.find_overlapping(-50, -100, width + 50, -5):
                if "ambient_particle" in self.preview_canvas.gettags(item):
                    self.preview_canvas.delete(item)
                    
            # Hard limit rendering counts to prevent lag spikes
            weather_items = self.preview_canvas.find_withtag("weather")
            if len(weather_items) > 300:
                self.preview_canvas.delete(*weather_items[:-300]) # Instantly deletes the oldest items
                
            particle_items = self.preview_canvas.find_withtag("ambient_particle")
            if len(particle_items) > 300:
                self.preview_canvas.delete(*particle_items[:-300])
            
            # Spawn new weather based on climate configuration
            if self.has_precipitation.get():
                temp = self.temperature.get()
                downfall = self.downfall.get()
                spawn_count = int(downfall * 5)
                
                # Guarantee at least some spawn if downfall > 0
                if downfall > 0 and spawn_count == 0 and random.random() < downfall:
                    spawn_count = 1
                    
                for _ in range(spawn_count):
                    x = random.randint(0, width)
                    if temp >= 0.15: # Rain
                        self.preview_canvas.create_line(x, 0, x, 15, fill="#5599FF", width=2, tags=("weather", "rain"))
                    else: # Snow
                        self.preview_canvas.create_oval(x-2, -2, x+2, 2, fill="white", outline="", tags=("weather", "snow"))
                        
            # Spawn new ambient particles
            particle_type = self.ambient_particle.get()
            prob = self.particle_probability.get()
            
            if particle_type != "none" and prob > 0:
                # Scale probability up for visibility, but keep a sensible limit (max 10/frame)
                spawn_count = int(prob * 10)
                if random.random() < (prob * 10) % 1:
                    spawn_count += 1
                    
                for _ in range(spawn_count):
                    x = random.randint(0, width)
                    y = random.randint(height // 2, height)
                    color, direction = "white", "particle_up"
                    
                    if particle_type == "minecraft:ash":
                        color = "#777777"
                    elif particle_type == "minecraft:white_ash":
                        color = "#E0E0E0"
                    elif particle_type == "minecraft:crimson_spore":
                        color = "#AA2222"
                    elif particle_type == "minecraft:warped_spore":
                        color = "#22AAAA"
                    elif particle_type == "minecraft:falling_spore_blossom":
                        color = "#55FF55"
                        direction = "particle_down"
                        y = random.randint(0, height // 2)
                        
                    self.preview_canvas.create_oval(x-1, y-1, x+1, y+1, fill=color, outline="", tags=("ambient_particle", direction))

        # Loop animation at ~20 FPS (50ms)
        self.root.after(50, self.animate)

if __name__ == "__main__":
    try:
        root = tk.Tk()
        if not HAS_PILLOW:
            root.withdraw() # Hide the main window
            error_text = f"Dependency Missing: Please run 'pip install Pillow' in your terminal!\n\nError Details:\n{PILLOW_ERROR}"
            print(error_text)
            messagebox.showerror("Dependency Missing", error_text)
            root.destroy()
            input("Press Enter to exit...")
        else:
            app = BiomeConfiguratorApp(root)
            root.mainloop()
    except Exception as e:
        error_message = traceback.format_exc()
        
        # Save the crash to a text file so it can't disappear
        with open("crash_report.txt", "w") as f:
            f.write("FATAL CRASH LOG:\n")
            f.write(error_message)
            
        print("\n==================================")
        print("FATAL CRASH DETECTED!")
        print("==================================")
        print(error_message)
        
        try:
            # Attempt to show the crash in a UI window so it doesn't just silently disappear
            if 'root' not in locals() or not root.winfo_exists():
                root = tk.Tk()
                root.withdraw()
            messagebox.showerror("Crash Report", f"The application encountered a fatal error:\n\n{error_message}")
        except:
            pass
            
        input("Press Enter to exit...")
