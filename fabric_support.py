"""Fabric 26.3 project inspection and reversible biome/content export.

This extension is part of the GPL-3.0 Biome Configurator fork.
It never executes a selected project's scripts or modifies source textures.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import copy
import hashlib
import io
import json
import os
import re
import tempfile
import uuid

from PIL import Image, ImageOps

MC_VERSION = "26.3"
TERRA_VERSION = "26.3-26.3.0.0.9"
MANIFEST = ".biome-configurator.json"
NAMESPACE = re.compile(r"[a-z0-9_.-]+\Z")
RESOURCE_PATH = re.compile(r"[a-z0-9_./-]+\Z")


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def valid_path(value):
    if not RESOURCE_PATH.fullmatch(value) or any(p in ("", ".", "..") for p in value.split("/")):
        raise ValueError(f"Invalid Minecraft resource path: {value!r}. Use lowercase letters and underscores.")
    return value


def resource_id(value):
    parts = value.split(":")
    if len(parts) != 2 or not NAMESPACE.fullmatch(parts[0]):
        raise ValueError(f"Expected namespace:path, got {value!r}")
    valid_path(parts[1])
    return value


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def template(name):
    return copy.deepcopy(read_json(Path(__file__).with_name("minecraft_26_3_templates.json"))[name])


@dataclass
class FabricProject:
    root: Path
    namespace: str
    split_client: bool
    mod: dict

    @classmethod
    def inspect(cls, directory):
        root = Path(directory).resolve(strict=True)
        mod_path = root / "src/main/resources/fabric.mod.json"
        if not mod_path.is_file():
            raise ValueError("Choose the project folder containing src/main/resources/fabric.mod.json.")
        mod = read_json(mod_path)
        namespace = mod.get("id", "")
        if not NAMESPACE.fullmatch(namespace):
            raise ValueError("The Fabric mod ID is missing or invalid.")
        props_path = root / "gradle.properties"
        props = props_path.read_text(encoding="utf-8-sig") if props_path.exists() else ""
        version = re.search(r"(?m)^\s*minecraft_version\s*=\s*([^\s#]+)", props)
        if not version or version[1] != MC_VERSION:
            raise ValueError("This exporter currently supports minecraft_version=26.3 only.")
        build = root / "build.gradle"
        if not build.is_file():
            raise ValueError("This version requires a single-project Groovy build.gradle Fabric template.")
        build_text = build.read_text(encoding="utf-8-sig")
        if "fabric-loom" not in build_text:
            raise ValueError("The selected project does not appear to use Fabric Loom.")
        return cls(root, namespace, "splitEnvironmentSourceSets" in build_text, mod)

    @property
    def package(self):
        # Prefix prevents a namespace starting with a digit becoming an invalid Java package.
        return "biomeconfig.generated.m_" + re.sub(r"[^a-z0-9_]", "_", self.namespace)


ROLE_DEFAULTS = {
    "grass_top": "duskgrass_block_top.png",
    "grass_side": "duskgrass_block_side.png",
    "grass_overlay": "duskgrass_block_side_overlay.png",
    "dirt": "ash_dirt.png",
    "stone": "gloomstone.png",
    "deepstone": "deepstone.png",
    "short_grass": "gloam_short_grass.png",
    "dusk_grass": "ash_grass.png",
    "tall_bottom": "tall_duskgrass_bottom.png",
    "tall_top": "tall_duskgrass_top.png",
    "tree1_log": "gloom_oak_log.png",
    "tree1_top": "gloom_oak_log_top.png",
    "tree1_leaves": "gloom_oak_leaves.png",
    "tree2_log": "ashwood_log.png",
    "tree2_top": "ashwood_log_top.png",
    "tree2_leaves": "ashwood_leaves.png",
}
BLOCK_DEFAULTS = {
    "grass": "duskgrass_block", "dirt": "ash_dirt", "stone": "gloomstone",
    "deepstone": "deepstone", "short_grass": "gloam_short_grass", "dusk_grass": "ash_grass",
    "tall_grass": "tall_duskgrass", "tree1_log": "gloom_oak_log",
    "tree1_leaves": "gloom_oak_leaves", "tree2_log": "ashwood_log", "tree2_leaves": "ashwood_leaves",
}


def default_design(texture_dir=""):
    return {
        "biome": "gloam_woods", "texture_dir": str(texture_dir),
        "textures": dict(ROLE_DEFAULTS), "blocks": dict(BLOCK_DEFAULTS),
        "tint_grass": True, "tint_leaves": True,
        "tree1_count": 3, "tree2_count": 2, "plant_count": 12,
        "region_weight": 2, "base_biome": "minecraft:forest", "deep_y": 0,
        "colors": {"sky_color": "#8796a5", "fog_color": "#8b9297", "water_color": "#405b63",
                   "water_fog_color": "#253b42", "grass_color": "#75866d", "foliage_color": "#697d64"},
        "temperature": 0.6, "downfall": 0.7, "has_precipitation": True,
        "grass_color_modifier": "none", "mobs": [],
        "ambient_particle": "none", "particle_probability": 0,
        "ambient_loop": "none", "ambient_mood": "none", "ambient_additions": "none",
    }


def texture_path(design, role):
    root = Path(design["texture_dir"]).resolve(strict=True)
    filename = design["textures"].get(role, "")
    if not filename or Path(filename).suffix.lower() != ".png":
        raise ValueError(f"Choose a PNG for {role.replace('_', ' ')}.")
    path = (root / filename).resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError("Textures must be inside the selected texture folder.")
    with Image.open(path) as image:
        image.verify()
    return path


def is_tinted(design, role):
    return (design["tint_grass"] and role in {"grass_top", "grass_overlay", "short_grass", "dusk_grass", "tall_bottom", "tall_top"}) or (design["tint_leaves"] and role.endswith("_leaves"))


def texture_image(design, role, preview=False):
    with Image.open(texture_path(design, role)) as source:
        image = source.convert("RGBA")
    if preview:
        image = image.crop((0, 0, image.width, image.width)).resize((16, 16), Image.Resampling.NEAREST)
    if is_tinted(design, role):
        alpha = image.getchannel("A")
        image = ImageOps.grayscale(image).convert("RGBA")
        image.putalpha(alpha)
    return image


def validate_design(design):
    from worldgen_studio import settings, validate
    validate(settings(design))
    valid_path(design["biome"])
    if "/" in design["biome"]:
        raise ValueError("Use a simple biome name without slashes in this first version.")
    ids = list(design["blocks"].values())
    if len(ids) != len(set(ids)):
        raise ValueError("Each material needs a different block ID.")
    for block in ids:
        valid_path(block)
        if "/" in block:
            raise ValueError("Block names must not contain slashes.")
    for role in ROLE_DEFAULTS:
        texture_path(design, role)
    for value in design["colors"].values():
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            raise ValueError("Colors must use #RRGGBB.")
    if not -2 <= float(design["temperature"]) <= 2 or not 0 <= float(design["downfall"]) <= 1:
        raise ValueError("Temperature must be between -2 and 2; downfall between 0 and 1.")
    for key in ("tree1_count", "tree2_count", "plant_count"):
        if not 0 <= int(design[key]) <= 32:
            raise ValueError("Tree and plant counts must be between 0 and 32.")
    if not 1 <= int(design["region_weight"]) <= 100:
        raise ValueError("Region weight must be between 1 and 100.")
    if not -59 <= int(design["deep_y"]) <= 128:
        raise ValueError("The deep stone transition must be between Y=-59 and Y=128.")
    resource_id(design["base_biome"])
    if design["base_biome"] not in {"minecraft:forest", "minecraft:dark_forest", "minecraft:taiga", "minecraft:plains"}:
        raise ValueError("Choose one of the supported Overworld placement templates.")


def build_biome(design, namespace, studio=False):
    """Use 26.3 environment attributes, not removed legacy spawn/effect fields."""
    attrs = {f"minecraft:visual/{key}": value.lower() for key, value in design["colors"].items()
             if key in {"sky_color", "fog_color", "water_fog_color"}}
    spawns = {key: [] for key in ("ambient", "axolotls", "creature", "misc", "monster", "underground_water_creature", "water_ambient", "water_creature")}
    costs = {}
    for mob in design.get("mobs", []):
        resource_id(mob["type"])
        low, high = int(mob["minCount"]), int(mob["maxCount"])
        if not 1 <= low <= high <= 64 or int(mob["weight"]) <= 0:
            raise ValueError("Mob pack sizes must be 1..64 with min <= max and positive weights.")
        count = low if low == high else {"type": "minecraft:uniform", "min_inclusive": low, "max_inclusive": high}
        spawns.setdefault(mob["category"], []).append({"type": mob["type"], "count": count, "weight": int(mob["weight"])})
        if float(mob.get("charge", 0)) > 0:
            costs[mob["type"]] = {"energy_budget": float(mob["energy_budget"]), "charge": float(mob["charge"])}
    attrs["minecraft:gameplay/natural_mob_spawns"] = {"modifier": "overlay", "argument": {"spawns_by_category": spawns, "spawn_costs": costs}}
    attrs["minecraft:gameplay/creature_world_gen_spawn_probability"] = 0.1
    if design.get("ambient_particle", "none") != "none":
        resource_id(design["ambient_particle"])
        probability = float(design["particle_probability"])
        if not 0 <= probability <= 1:
            raise ValueError("Particle probability must be between 0 and 1.")
        attrs["minecraft:visual/ambient_particles"] = {"modifier": "append", "argument": [{"particle": {"type": design["ambient_particle"]}, "probability": probability}]}
    ambience = {}
    for setting, attribute in (("ambient_loop", "loop"), ("ambient_mood", "mood"), ("ambient_additions", "additions")):
        sound = design.get(setting, "none")
        if sound != "none":
            resource_id(sound)
            if attribute == "loop":
                ambience[attribute] = sound
            elif attribute == "mood":
                ambience[attribute] = {"sound": sound, "tick_delay": 6000, "block_search_extent": 8, "offset": 2.0}
            else:
                ambience[attribute] = {"sound": sound, "tick_chance": 0.0111}
    if ambience:
        attrs["minecraft:audio/ambient_sounds"] = ambience
    base = template("forest")
    effects = {key: value for key, value in design["colors"].items() if key in {"water_color", "grass_color", "foliage_color"}}
    if design.get("grass_color_modifier", "none") != "none":
        effects["grass_color_modifier"] = design["grass_color_modifier"]
    base.update({"attributes": attrs, "effects": effects, "temperature": float(design["temperature"]),
                 "downfall": float(design["downfall"]), "has_precipitation": bool(design["has_precipitation"])})
    base["features"][9] = [f"{namespace}:bc/{design['biome']}/{name}" for name in ("tree1", "tree2", "short_grass", "dusk_grass", "tall_grass")]
    from worldgen_studio import settings
    config = settings(design)
    if studio and config["terrain"] != "Vanilla Overworld":
        base["carvers"] = []
    if not config["vanilla_ores"]:
        base["features"][6] = []
    for flag,index in (("lakes",1),("geodes",2),("dungeons",3),("springs",8)):
        if not config[flag]:base["features"][index]=[]
    base["features"][6] += [f"{namespace}:bc/{design['biome']}/ore_{ore['name']}" for ore in config["ores"] if ore["count"] > 0]
    return base


def material_definitions(design):
    blocks = design["blocks"]
    return {blocks[key]: {"kind": kind, "roles": roles, "tinted": bool(tinted)} for key, kind, roles, tinted in [
        ("dirt", "dirt", {"all": "dirt"}, False),
        ("stone", "stone", {"all": "stone"}, False),
        ("deepstone", "deepstone", {"all": "deepstone"}, False),
        ("grass", "grass", {"top": "grass_top", "side": "grass_side", "overlay": "grass_overlay", "bottom": "dirt"}, design["tint_grass"]),
        ("short_grass", "plant", {"cross": "short_grass"}, design["tint_grass"]),
        ("dusk_grass", "plant", {"cross": "dusk_grass"}, design["tint_grass"]),
        ("tall_grass", "tall", {"bottom": "tall_bottom", "top": "tall_top"}, design["tint_grass"]),
        ("tree1_log", "log", {"side": "tree1_log", "end": "tree1_top"}, False),
        ("tree1_leaves", "leaves", {"all": "tree1_leaves"}, design["tint_leaves"]),
        ("tree2_log", "log", {"side": "tree2_log", "end": "tree2_top"}, False),
        ("tree2_leaves", "leaves", {"all": "tree2_leaves"}, design["tint_leaves"]),
    ]}


@dataclass
class ExportPlan:
    project: FabricProject
    files: dict[str, bytes] = field(default_factory=dict)
    previous: dict = field(default_factory=dict)
    expected: dict[str, str | None] = field(default_factory=dict)
    merged_paths: set[str] = field(default_factory=set)

    def put(self, path, value):
        path = str(path).replace("\\", "/")
        target = self.project.root / path
        if not target.resolve().is_relative_to(self.project.root):
            raise ValueError("Export path escapes the project.")
        data = value if isinstance(value, bytes) else json_bytes(value)
        if path in self.files and self.files[path] != data:
            raise ValueError(f"Two designs disagree about {path}. Give their materials different IDs.")
        self.files[path] = data

    def merge_json(self, path, updater):
        target = self.project.root / path
        data = read_json(target) if target.exists() else {}
        updater(data)
        self.put(path, data)
        self.merged_paths.add(path)

    def seal(self):
        managed = self.previous.get("managed", {})
        for path, data in self.files.items():
            target = self.project.root / path
            old = target.read_bytes() if target.exists() else None
            self.expected[path] = digest(old) if old is not None else None
            if old is not None and old != data and path in managed and path not in self.merged_paths and digest(old) != managed[path]:
                raise ValueError(f"You edited a generated file: {path}. Export stopped to preserve your changes.")
            if old is not None and old != data and path not in managed:
                allowed = path in {"src/main/resources/fabric.mod.json", "build.gradle", MANIFEST} or "/tags/" in path or "/lang/" in path
                if not allowed:
                    raise ValueError(f"An existing file would be replaced: {path}. Choose a different ID.")
        return self

    def changes(self):
        return [("create" if self.expected[path] is None else "update", path) for path, data in self.files.items()
                if self.expected[path] != digest(data)]

    def apply(self):
        """Recheck after review, back up all changes, and restore on a write failure."""
        for path, expected in self.expected.items():
            target = self.project.root / path
            actual = digest(target.read_bytes()) if target.exists() else None
            if actual != expected:
                raise ValueError(f"File changed after the export review: {path}. Review again.")
        changes = self.changes()
        if not changes:
            return None
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
        backup = self.project.root / ".biome-configurator-backups" / stamp
        backup.mkdir(parents=True, exist_ok=False)
        originals = {}
        for _, path in changes:
            target = self.project.root / path
            old = target.read_bytes() if target.exists() else None
            originals[path] = old
            if old is not None:
                saved = backup / "originals" / path
                saved.parent.mkdir(parents=True, exist_ok=True)
                saved.write_bytes(old)
        (backup / "changes.json").write_bytes(json_bytes({"changes": changes, "before": self.expected}))
        written = []
        try:
            for _, path in changes:
                target = self.project.root / path
                target.parent.mkdir(parents=True, exist_ok=True)
                # Reserve the recovery record before attempting a write.
                written.append(path)
                atomic_write(target, self.files[path])
        except Exception:
            for path in reversed(written):
                target = self.project.root / path
                if target.exists():
                    failed = backup / "interrupted-export" / path
                    failed.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(target, failed)
                if originals[path] is not None:
                    target.write_bytes(originals[path])
            raise
        return backup


def atomic_write(path, data):
    descriptor, temporary = tempfile.mkstemp(prefix=".bc-", dir=path.parent)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
    os.replace(temporary, path)


def build_plan(project, design):
    validate_design(design)
    prior_path = project.root / MANIFEST
    previous = read_json(prior_path) if prior_path.exists() else {}
    if previous and previous.get("format") != 1:
        raise ValueError("This project's exporter manifest version is not supported.")
    designs = copy.deepcopy(previous.get("designs", {}))
    designs[design["biome"]] = copy.deepcopy(design)
    plan = ExportPlan(project, previous=previous)
    all_materials = {}
    ns = project.namespace
    resources = "src/main/resources"
    for current in designs.values():
        validate_design(current)
        mats = material_definitions(current)
        for block, definition in mats.items():
            normalized = {"kind": definition["kind"], "tinted": definition["tinted"], "textures": {}}
            for slot, role in definition["roles"].items():
                source = texture_path(current, role)
                # Role-specific names avoid tint conversion affecting a different material.
                name = f"bc/{block}_{slot}"
                normalized["textures"][slot] = f"{ns}:block/{name}"
                if is_tinted(current, role):
                    buffer = io.BytesIO()
                    texture_image(current, role).save(buffer, format="PNG")
                    content = buffer.getvalue()
                else:
                    content = source.read_bytes()
                target = f"{resources}/assets/{ns}/textures/block/{name}.png"
                plan.put(target, content)
                metadata = source.with_name(source.name + ".mcmeta")
                if metadata.exists():
                    read_json(metadata)
                    plan.put(target + ".mcmeta", metadata.read_bytes())
            if block in all_materials and all_materials[block] != normalized:
                raise ValueError(f"Material {block} differs between biomes. Give it a unique block ID.")
            all_materials[block] = normalized
        emit_biome(plan, current)
    for block, material in all_materials.items():
        emit_block(plan, block, material)
    emit_java(plan, all_materials, designs)
    emit_tags(plan, all_materials, designs)
    emit_integration(plan)
    managed = dict(previous.get("managed", {}))
    managed.update({path: digest(data) for path, data in plan.files.items()})
    plan.put(MANIFEST, {"format": 1, "minecraft": MC_VERSION, "designs": designs, "managed": managed})
    return plan.seal()


def emit_block(plan, block, mat):
    ns = plan.project.namespace
    root = f"src/main/resources/assets/{ns}"
    kind, textures, tinted = mat["kind"], mat["textures"], mat["tinted"]
    model = f"{ns}:block/{block}"
    variants = {"": {"model": model}}
    if kind == "log":
        data = {"parent": "minecraft:block/cube_column", "textures": textures}
        variants = {"axis=y": {"model": model}, "axis=x": {"model": model, "x": 90, "y": 90}, "axis=z": {"model": model, "x": 90}}
    elif kind == "grass":
        data = template("grass_model")
        data["textures"] = {**textures, "particle": textures["bottom"]}
        if not tinted:
            for element in data["elements"]:
                for face in element["faces"].values():
                    face.pop("tintindex", None)
    elif kind == "tall":
        parent = "minecraft:block/tinted_cross" if tinted else "minecraft:block/cross"
        for half, slot in (("lower", "bottom"), ("upper", "top")):
            plan.put(f"{root}/models/block/{block}_{half}.json", {"parent": parent, "textures": {"cross": textures[slot]}})
        variants = {f"half={half}": {"model": model + "_" + half} for half in ("lower", "upper")}
        data = {"parent": model + "_lower"}
    elif kind == "plant":
        data = {"parent": "minecraft:block/tinted_cross" if tinted else "minecraft:block/cross", "textures": textures}
    elif kind == "leaves" and tinted:
        data = {"parent": "minecraft:block/leaves", "textures": textures}
    else:
        data = {"parent": "minecraft:block/cube_all", "textures": textures}
    plan.put(f"{root}/models/block/{block}.json", data)
    plan.put(f"{root}/blockstates/{block}.json", {"variants": variants})
    item = {"type": "minecraft:model", "model": model}
    if tinted:
        item["tints"] = [{"type": "minecraft:constant", "value": "#77ab2f" if kind == "leaves" else "#91bd59"}]
    plan.put(f"{root}/items/{block}.json", {"model": item})
    entry = {"type": "minecraft:item", "name": f"{ns}:{block}"}
    conditions = [{"condition": "minecraft:survives_explosion"}]
    if kind == "tall":
        conditions.append({"condition": "minecraft:block_state_property", "block": f"{ns}:{block}", "properties": {"half": "lower"}})
    plan.put(f"src/main/resources/data/{ns}/loot_table/blocks/{block}.json", {"type": "minecraft:block", "pools": [{"rolls": 1, "entries": [entry], "conditions": conditions}]})


def emit_biome(plan, design):
    ns, biome = plan.project.namespace, design["biome"]
    base = f"src/main/resources/data/{ns}"
    ids = {key: f"{ns}:{value}" for key, value in design["blocks"].items()}
    plan.put(f"{base}/worldgen/biome/{biome}.json", build_biome(design, ns))
    for tree in ("tree1", "tree2"):
        feature = template("oak")
        feature["trunk_provider"] = {"id": ids[tree + "_log"], "properties": {"axis": "y"}}
        feature["foliage_provider"] = {"id": ids[tree + "_leaves"], "properties": {"distance": "7", "persistent": "false", "waterlogged": "false"}}
        feature["below_trunk_provider"] = {"id": ids["dirt"]}
        plan.put(f"{base}/worldgen/feature/bc/{biome}/{tree}.json", feature)
        placement = [{"type": "minecraft:count", "count": int(design[tree + "_count"])}, {"type": "minecraft:in_square"},
                     {"type": "minecraft:surface_water_depth_filter", "max_water_depth": 0},
                     {"type": "minecraft:heightmap", "heightmap": "OCEAN_FLOOR"}, {"type": "minecraft:biome"}]
        plan.put(f"{base}/worldgen/placed_feature/bc/{biome}/{tree}.json", {"feature": f"{ns}:bc/{biome}/{tree}", "placement": placement})
    for name in ("short_grass", "dusk_grass", "tall_grass"):
        state = {"id": ids[name]}
        if name == "tall_grass":
            state["properties"] = {"half": "lower"}
        plan.put(f"{base}/worldgen/feature/bc/{biome}/{name}.json", {"type": "minecraft:simple_block", "to_place": state})
        plan.put(f"{base}/worldgen/placed_feature/bc/{biome}/{name}.json", {"feature": f"{ns}:bc/{biome}/{name}", "placement": [
            {"type": "minecraft:count", "count": int(design["plant_count"])}, {"type": "minecraft:in_square"},
            {"type": "minecraft:heightmap", "heightmap": "WORLD_SURFACE_WG"}, {"type": "minecraft:biome"},
            {"type": "minecraft:block_predicate_filter", "predicate": {"type": "minecraft:matching_block_tag", "tag": "minecraft:air"}},
        ]})
    # A dedicated preview world type uses our material rule even without TerraBlender's multi-noise biome source.
    from worldgen_studio import settings, noise_settings, ore_resources
    config = settings(design)
    if config["terrain"] != "Vanilla Overworld":
        plan.put(f"{base}/worldgen/biome/{biome}_studio.json", build_biome(design, ns, studio=True))
    noise = noise_settings(template("noise_settings"), config, f"{ns}:bc_surface")
    plan.put(f"{base}/worldgen/noise_settings/bc/{biome}_preview.json", noise)
    preset = template("world_preset")
    generator = preset["dimensions"]["minecraft:overworld"]["generator"]
    generator["settings"] = f"{ns}:bc/{biome}_preview"
    studio_biome=biome+"_studio" if config["terrain"]!="Vanilla Overworld" else biome
    generator["biome_source"] = {"type": "minecraft:fixed", "biome": f"{ns}:{studio_biome}"}
    plan.put(f"{base}/worldgen/world_preset/{biome}_preview.json", preset)
    for ore in config["ores"]:
        feature, placement = ore_resources(ore)
        key = f"bc/{biome}/ore_{ore['name']}"
        plan.put(f"{base}/worldgen/feature/{key}.json", feature)
        plan.put(f"{base}/worldgen/placed_feature/{key}.json", {"feature": f"{ns}:{key}", "placement": placement})
    if config["dimension"]:
        plan.put(f"{base}/dimension/{config['dimension_id']}.json", {"type": "minecraft:overworld", "generator": generator})


def emit_tags(plan, materials, designs):
    ns = plan.project.namespace
    def tag(name, values):
        path = f"src/main/resources/data/minecraft/tags/{name}.json"
        def merge(data):
            data.setdefault("replace", False)
            entries = data.setdefault("values", [])
            for value in values:
                if value not in entries:
                    entries.append(value)
        plan.merge_json(path, merge)
    for name, kinds in {"mineable/shovel": {"dirt", "grass"}, "mineable/pickaxe": {"stone", "deepstone"},
                        "mineable/axe": {"log"}, "mineable/hoe": {"leaves"}, "logs": {"log"},
                        "logs_that_burn": {"log"}, "leaves": {"leaves"}, "dirt": {"dirt", "grass"},
                        "animals_spawnable_on": {"grass"}, "base_stone_overworld": {"stone", "deepstone"},
                        "stone_ore_replaceables": {"stone"}, "deepslate_ore_replaceables": {"deepstone"}}.items():
        tag("block/" + name, [f"{ns}:{name_}" for name_, mat in materials.items() if mat["kind"] in kinds])
    # 26.3 heightmap predicates use data-driven motion tags, not copied Block properties.
    tag("block/blocks_motion", [f"{ns}:{name}" for name,mat in materials.items() if mat["kind"] not in {"plant","tall"}])
    from worldgen_studio import settings
    biome_ids = [f"{ns}:{biome}" for biome in designs]
    biome_ids += [f"{ns}:{biome}_studio" for biome,design in designs.items() if settings(design)["terrain"]!="Vanilla Overworld"]
    tag("worldgen/biome/is_overworld", biome_ids)
    tag("worldgen/biome/is_forest", biome_ids)
    tag("worldgen/world_preset/normal", [f"{ns}:{biome}_preview" for biome in designs])
    def lang(data):
        for block in materials:
            data.setdefault(f"block.{ns}.{block}", block.replace("_", " ").title())
        for biome in designs:
            data.setdefault(f"biome.{ns}.{biome}", biome.replace("_", " ").title())
            if settings(designs[biome])["terrain"]!="Vanilla Overworld":
                data.setdefault(f"biome.{ns}.{biome}_studio", biome.replace("_", " ").title())
            data.setdefault(f"generator.{ns}.{biome}_preview", biome.replace("_", " ").title() + " Preview")
    plan.merge_json(f"src/main/resources/assets/{ns}/lang/en_us.json", lang)


def emit_integration(plan):
    project, ns = plan.project, plan.project.namespace
    def mod(data):
        entries = data.setdefault("entrypoints", {})
        for kind, suffix in (("main", "GeneratedContent"), ("client", "GeneratedClient"), ("terrablender", "GeneratedWorldgen")):
            items = entries.setdefault(kind, [])
            if not isinstance(items, list):
                raise ValueError(f"The existing {kind} entrypoint is not a list.")
            name = project.package + "." + suffix
            if name not in items:
                items.append(name)
        deps = data.setdefault("depends", {})
        deps.setdefault("terrablender", ">=26.3.0.0.9")
        deps.setdefault("fabric-api", ">=0.162.0")
    plan.merge_json("src/main/resources/fabric.mod.json", mod)
    build_path = project.root / "build.gradle"
    build = build_path.read_text(encoding="utf-8-sig")
    marker = "apply from: 'biome-configurator.gradle'"
    if marker not in build:
        build = build.rstrip() + "\n\n// Generated biome/content integration.\n" + marker + "\n"
    plan.put("build.gradle", build.encode("utf-8"))
    plan.merged_paths.add("build.gradle")
    script = f'''// Biome Configurator Fabric 26.3. TerraBlender is included in the built mod JAR.
repositories {{ maven {{ url = 'https://maven.minecraftforge.net/' }} }}
dependencies {{
    implementation("net.fabricmc.fabric-api:fabric-api:0.162.0+26.3")
    include implementation("com.github.glitchfiend:TerraBlender-fabric:{TERRA_VERSION}")
}}
'''
    plan.put("biome-configurator.gradle", script.encode())


def emit_java(plan, materials, designs):
    from java_templates import content_java, client_java, worldgen_java, surface_rule
    project = plan.project
    path = project.package.replace(".", "/")
    plan.put(f"src/main/java/{path}/GeneratedContent.java", content_java(project, materials).encode())
    client = "client" if project.split_client else "main"
    plan.put(f"src/{client}/java/{path}/GeneratedClient.java", client_java(project, materials).encode())
    plan.put(f"src/main/java/{path}/GeneratedWorldgen.java", worldgen_java(project, designs).encode())
    plan.put(f"src/main/resources/data/{project.namespace}/worldgen/material_rule/bc_surface.json", surface_rule(project, designs))
