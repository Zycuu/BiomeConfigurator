"""Shared, exportable world-generation model. Preview and export use the same density graph."""

import copy
import math
import re

TERRAIN_TYPES = (
    "Vanilla Overworld",
    "Flatlands",
    "Rolling Hills",
    "Mountains",
    "Ridged Highlands",
    "Plateaus",
    "Dunes",
    "Archipelago",
    "Ocean Basins",
    "Canyons",
    "Floating Islands",
)
CAVE_TYPES = ("None", "Tunnels", "Chambers", "Mixed")


def defaults():
    return {
        "terrain": "Vanilla Overworld",
        "base_height": 72,
        "mountain_height": 80,
        "wavelength": 320,
        "detail": 8,
        "sea_level": 63,
        "cave_type": "Mixed",
        "cave_density": 0.5,
        "cave_size": 1,
        "cave_min_y": -56,
        "cave_max_y": 48,
        "vanilla_ores": True,
        "ores": [],
        "dimension": False,
        "dimension_id": "",
        "island_thickness": 28,
        "terrace_height": 16,
        "fluid": "Water",
        "lakes": True,
        "geodes": True,
        "dungeons": True,
        "springs": True,
    }


def settings(design):
    result = defaults()
    result.update(copy.deepcopy(design.get("worldgen", {})))
    return result


def preset(kind):
    config = defaults()
    profiles = {
        "Flatlands": dict(
            base_height=72, mountain_height=0, detail=0, cave_type="None"
        ),
        "Rolling Hills": dict(mountain_height=64, detail=4),
        "Mountains": dict(
            base_height=84, mountain_height=120, wavelength=480, detail=10
        ),
        "Ridged Highlands": dict(
            base_height=60, mountain_height=72, wavelength=480, detail=5
        ),
        "Plateaus": dict(
            base_height=88, mountain_height=96, detail=0, terrace_height=16
        ),
        "Dunes": dict(
            base_height=64,
            mountain_height=24,
            wavelength=128,
            detail=1,
            cave_type="None",
        ),
        "Archipelago": dict(
            base_height=52, mountain_height=72, wavelength=256, detail=4
        ),
        "Ocean Basins": dict(base_height=30, mountain_height=40, detail=3),
        "Canyons": dict(base_height=72, mountain_height=72, wavelength=320, detail=2),
        "Floating Islands": dict(
            base_height=140,
            mountain_height=32,
            wavelength=192,
            detail=4,
            island_thickness=28,
            cave_type="None",
            fluid="Air",
            sea_level=-60,
        ),
    }
    config.update(profiles.get(kind, {}))
    config["terrain"] = kind
    return config


def validate(config):
    if config["terrain"] not in TERRAIN_TYPES or config["cave_type"] not in CAVE_TYPES:
        raise ValueError("Choose a supported terrain and cave preset.")
    if config["fluid"] not in ("Water", "Lava", "Air"):
        raise ValueError("Choose Water, Lava, or Air for the sea fluid.")
    ranges = {
        "base_height": (-32, 224),
        "mountain_height": (0, 160),
        "wavelength": (32, 2048),
        "detail": (0, 32),
        "sea_level": (-60, 160),
        "cave_density": (0, 1),
        "cave_size": (0.25, 4),
        "cave_min_y": (-60, 240),
        "cave_max_y": (-56, 280),
        "island_thickness": (8, 96),
        "terrace_height": (4, 64),
    }
    for key, (low, high) in ranges.items():
        value = float(config[key])
        if not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"{key.replace('_',' ').title()} must be {low} to {high}.")
    if config["cave_min_y"] >= config["cave_max_y"]:
        raise ValueError("Cave minimum Y must be below maximum Y.")
    if len(config["ores"]) > 32:
        raise ValueError("Use at most 32 ore rules per biome.")
    for ore in config["ores"]:
        if not re.fullmatch(r"[a-z0-9_]+", ore["name"]) or not re.fullmatch(
            r"[a-z0-9_.-]+:[a-z0-9_./-]+", ore["block"]
        ):
            raise ValueError(
                "Ore names and namespace:block IDs must be lowercase resource IDs."
            )
        if not -60 <= int(ore["min_y"]) <= int(ore["max_y"]) <= 300:
            raise ValueError(
                "Ore heights must satisfy -60 <= minimum <= maximum <= 300."
            )
        if not 0 <= int(ore["count"]) <= 64 or not 1 <= int(ore["size"]) <= 64:
            raise ValueError("Ore attempts must be 0..64 and vein size 1..64.")
        if (
            ore["distribution"] not in ("Uniform", "Triangle")
            or not 0 <= float(ore["discard"]) <= 1
        ):
            raise ValueError(
                "Choose Uniform/Triangle and an air-exposure discard chance from 0 to 1."
            )
    if len({ore["name"] for ore in config["ores"]}) != len(config["ores"]):
        raise ValueError("Each ore rule needs a unique name.")
    if config["dimension"] and not re.fullmatch(r"[a-z0-9_]+", config["dimension_id"]):
        raise ValueError("Enter a simple lowercase name for the new dimension.")
    return config


def binary(kind, left, right):
    return {"type": "minecraft:" + kind, "left": left, "right": right}


def unary(kind, value):
    return {"type": "minecraft:" + kind, "input": value}


def gradient(y0, y1, v0, v1):
    return {
        "type": "minecraft:gradient",
        "axis": "y",
        "from_coordinate": y0,
        "to_coordinate": y1,
        "from_value": v0,
        "to_value": v1,
    }


def noise(name, xz, y=0):
    return {
        "type": "minecraft:noise",
        "noise": "minecraft:" + name,
        "xz_scale": xz,
        "y_scale": y,
    }


def density(config):
    """All heights are density amplitudes in blocks, not promises of an exact maximum peak."""
    validate(config)
    add = lambda a, b: binary("add", a, b)
    mul = lambda a, b: binary("mul", a, b)
    kind = config["terrain"]
    base, amp = config["base_height"], config["mountain_height"]
    scale = 512 / config["wavelength"]
    broad = noise("continentalness", scale)
    ridges = unary("abs", noise("ridge", scale * 1.6))
    detail = mul(noise("surface", scale * 4), config["detail"])
    relief = mul(broad, amp)
    if kind == "Flatlands":
        relief = 0
        detail = 0
    elif kind == "Rolling Hills":
        relief = mul(broad, amp * 0.45)
    elif kind == "Ridged Highlands":
        relief = mul(add(1, mul(ridges, -1.5)), amp)
    elif kind == "Plateaus":
        # Interval terraces are true horizontal shelves in the density function.
        terrace = config["terrace_height"]
        relief = -amp
        for level in range(-4, 5):
            relief = {
                "type": "minecraft:range_choice",
                "input": broad,
                "min_inclusive": level * 0.18,
                "max_exclusive": (level + 1) * 0.18,
                "when_in_range": level * terrace,
                "when_out_of_range": relief,
            }
    elif kind == "Dunes":
        relief = mul(unary("abs", noise("ridge", scale * 3)), amp * 0.6)
        detail = mul(noise("surface", scale * 8), config["detail"] * 0.15)
    elif kind == "Archipelago":
        relief = add(mul(broad, amp * 1.8), -amp * 0.35)
    elif kind == "Ocean Basins":
        relief = add(mul(broad, amp * 0.6), -amp * 0.5)
    elif kind == "Canyons":
        channel = {
            "type": "minecraft:clamp",
            "input": mul(ridges, 5),
            "min": 0,
            "max": 1,
        }
        relief = add(mul(channel, amp), -amp * 0.6)
    elevation = add(add(base, relief), detail)
    surface = add(mul(elevation, 1 / 64), gradient(-64, 320, 1, -5))
    # gradient above is -Y/64 exactly throughout the build range.
    if kind == "Floating Islands":
        thickness = config["island_thickness"]
        bottom = add(
            gradient(-64, 320, -1, 5), mul(add(elevation, -thickness), -1 / 64)
        )
        surface = binary("min", surface, bottom)
        # Isolated land masses instead of a continuous hovering plate.
        surface = binary("min", surface, add(broad, 0.10))
    cave = config["cave_type"]
    if cave != "None" and config["cave_density"] > 0:
        frequency = 1 / config["cave_size"]
        tunnel = add(
            binary(
                "max",
                unary("abs", noise("spaghetti_3d_1", frequency, frequency)),
                unary("abs", noise("spaghetti_3d_2", frequency, frequency)),
            ),
            -(0.025 + config["cave_density"] * 0.22),
        )
        chamber = add(
            noise("cave_cheese", frequency, frequency),
            0.55 - config["cave_density"] * 0.65,
        )
        hollow = (
            tunnel
            if cave == "Tunnels"
            else chamber if cave == "Chambers" else binary("min", tunnel, chamber)
        )
        band = binary(
            "max",
            gradient(config["cave_min_y"] - 4, config["cave_min_y"], 1, -1),
            gradient(config["cave_max_y"], config["cave_max_y"] + 4, -1, 1),
        )
        surface = binary("min", surface, binary("max", hollow, band))
    # Preserve a solid bedrock floor and clear the top of the build limit.
    if kind != "Floating Islands":
        surface = binary("max", surface, gradient(-64, -60, 1, -1))
    return {
        "type": "minecraft:interpolated",
        "cell_size_xz": 4,
        "cell_size_y": 4,
        "input": surface,
    }


def noise_settings(template, config, material_rule="minecraft:overworld"):
    result = copy.deepcopy(template)
    if config["terrain"] != "Vanilla Overworld":
        result["noise_router"]["final_density"] = density(config)
        result["noise_router"]["chunk_surface_level"] = {
            "type": "minecraft:find_top_surface",
            "density": density(dict(config, cave_type="None")),
            "upper_bound": 320,
            "lower_bound": -64,
            "cell_height": 4,
        }
        # The custom terrain does not inherit vanilla aquifers; water fills below sea level.
        result.pop("aquifers", None)
        if config["terrain"] == "Floating Islands":
            result["default_fluid"] = "minecraft:air"
    result["sea_level"] = int(config["sea_level"])
    result["default_fluid"] = "minecraft:" + config["fluid"].lower()
    if config["terrain"] == "Floating Islands":
        result["default_fluid"] = "minecraft:air"
    result["material_rule"] = material_rule
    return result


def ore_resources(ore):
    feature = {
        "type": "minecraft:ore",
        "size": int(ore["size"]),
        "discard_chance_on_air_exposure": float(ore["discard"]),
        "targets": [
            {
                "state": ore["block"],
                "target": {
                    "predicate_type": "minecraft:tag_match",
                    "tag": "minecraft:base_stone_overworld",
                },
            }
        ],
    }
    height = {
        "type": (
            "minecraft:uniform"
            if ore["distribution"] == "Uniform"
            else "minecraft:trapezoid"
        ),
        "min_inclusive": {"absolute": int(ore["min_y"])},
        "max_inclusive": {"absolute": int(ore["max_y"])},
    }
    placement = [
        {"type": "minecraft:count", "count": int(ore["count"])},
        {"type": "minecraft:in_square"},
        {"type": "minecraft:height_range", "height": height},
        {"type": "minecraft:biome"},
    ]
    return feature, placement
