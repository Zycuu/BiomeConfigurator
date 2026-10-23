"""Run our bridge against the user's cached vanilla Minecraft, without running mod code."""

from dataclasses import dataclass
from pathlib import Path
import json
import os
import re
import subprocess
import threading
import time
import uuid
import zipfile


def minecraft_seed(text):
    text = str(text).strip()
    try:
        value = int(text)
        if -(1 << 63) <= value < (1 << 63):
            return value
    except ValueError:
        pass
    if not text:
        raise ValueError("Enter a seed, such as 0, 42, or Far Dark.")
    value = 0
    raw = text.encode("utf-16-be", errors="surrogatepass")
    for index in range(0, len(raw), 2):
        value = (
            31 * value + int.from_bytes(raw[index : index + 2], "big")
        ) & 0xFFFFFFFF
    return value if value < (1 << 31) else value - (1 << 32)


@dataclass(frozen=True)
class SampleRequest:
    seed: int = 0
    center_x: int = 0
    center_z: int = 0
    span: int = 256
    grid: int = 33

    def validate(self):
        if not -(1 << 63) <= self.seed < (1 << 63):
            raise ValueError("Seed is outside Java's signed 64-bit range.")
        if self.span not in (32, 64, 128, 256, 512, 1024, 2048) or self.grid not in (
            33,
            65,
            129,
        ):
            raise ValueError("Unsupported area or detail setting.")
        if self.span % (self.grid - 1):
            raise ValueError("Area must divide evenly into the sample grid.")
        if max(abs(self.center_x), abs(self.center_z)) + self.span > 30000000:
            raise ValueError(
                "The sampled area must stay within Minecraft's world border."
            )
        return self


def validate_sample(data):
    request = SampleRequest(
        int(data["seed"]),
        data["center_x"],
        data["center_z"],
        data["span"],
        data["grid"],
    ).validate()
    heights = data["heights"]
    if data.get("format") != 1 or data.get("minecraft") != "26.3":
        raise ValueError("This is not a Minecraft 26.3 terrain sample.")
    if len(heights) != request.grid or any(len(row) != request.grid for row in heights):
        raise ValueError("Incomplete terrain sample.")
    values = [h for row in heights for h in row]
    if any(type(h) is not int or not -64 <= h <= 320 for h in values):
        raise ValueError("Invalid terrain heights.")
    if min(values) != data["min_height"] or max(values) != data["max_height"]:
        raise ValueError("Terrain sample statistics do not match its heights.")
    if (
        data["step"] != request.span // (request.grid - 1)
        or data["origin_x"] != request.center_x - request.span // 2
        or data["origin_z"] != request.center_z - request.span // 2
    ):
        raise ValueError("Terrain sample coordinates do not match its settings.")
    if "columns" in data:
        import base64

        columns = data["columns"]
        if len(columns) != request.grid or any(
            len(row) != request.grid for row in columns
        ):
            raise ValueError("Incomplete voxel column sample.")
        for row, heights_row in zip(columns, heights):
            for encoded, height in zip(row, heights_row):
                try:
                    bits = base64.b64decode(encoded, validate=True)
                except ValueError as error:
                    raise ValueError("Invalid voxel column encoding.") from error
                if (
                    len(bits) != 48
                    or int.from_bytes(bits, "little").bit_length() - 64 != height
                ):
                    raise ValueError(
                        "Voxel occupancy does not match the sampled height."
                    )
    return data


def discover_runtime(home=None, environ=None):
    home, env = Path(home or Path.home()), (
        environ if environ is not None else os.environ
    )
    java_homes = [Path(env["JAVA_HOME"])] if env.get("JAVA_HOME") else []
    java_homes += sorted((home / ".jdks").glob("*"), reverse=True)
    java = None
    for candidate in java_homes:
        release = candidate / "release"
        executable = candidate / "bin" / ("java.exe" if os.name == "nt" else "java")
        if (
            release.is_file()
            and executable.is_file()
            and re.search(r'JAVA_VERSION="25(?:\.|"|\+)', release.read_text())
        ):
            java = executable
            break
    if java is None:
        raise RuntimeError(
            "Java 25 was not found. Install a JDK 25 in IntelliJ (.jdks), or set JAVA_HOME to it."
        )
    cache = Path(env.get("GRADLE_USER_HOME", home / ".gradle")) / "caches"
    loom = cache / "fabric-loom/26.3"
    common, metadata = (
        loom / "minecraft-common.jar",
        loom / "mojang_minecraft_info.json",
    )
    if not common.is_file() or not metadata.is_file():
        raise RuntimeError(
            "Minecraft 26.3 is not cached. Run your Fabric 26.3 development client once, then try again."
        )
    with zipfile.ZipFile(common) as archive:
        if json.loads(archive.read("version.json"))["id"] != "26.3":
            raise RuntimeError("The cached game is not Minecraft 26.3.")
    paths = [Path(__file__).with_name("bridge") / "terrain-sampler-26.3.jar", common]
    if not paths[0].is_file():
        raise RuntimeError("The terrain bridge is missing from this app installation.")
    for library in json.loads(metadata.read_text())["libraries"]:
        artifact = library.get("downloads", {}).get("artifact")
        coordinates = library["name"].split(":")
        if not artifact or len(coordinates) != 3:
            continue
        # Native classifier jars and the macOS Objective-C bridge are not needed by server worldgen.
        if os.name == "nt" and coordinates[1] == "java-objc-bridge":
            continue
        group, name, version = coordinates
        matches = sorted(
            (cache / "modules-2/files-2.1" / group / name / version).glob(
                "*/" + Path(artifact["path"]).name
            )
        )
        if not matches:
            raise RuntimeError(
                f"Missing cached library {library['name']}. Run the development client to finish downloading its libraries."
            )
        paths.append(matches[0])
    return java, paths


class SampleCancelled(Exception):
    pass


def sample_terrain(
    request,
    directory,
    progress=lambda row, total: None,
    cancel=None,
    worldgen=None,
    volume=False,
):
    request.validate()
    cancel = cancel or threading.Event()
    java, paths = discover_runtime()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8]
    output, log = directory / (run_id + ".json"), directory / (run_id + ".log")
    command = [
        str(java),
        "-Xmx768m",
        "-Djava.awt.headless=true",
        "-cp",
        os.pathsep.join(map(str, paths)),
        "terrainbridge.TerrainSampler",
        str(request.seed),
        str(request.center_x),
        str(request.center_z),
        str(request.span),
        str(request.grid),
        str(output.resolve()),
    ]
    if worldgen is not None or volume:
        from fabric_support import template
        from worldgen_studio import defaults, noise_settings

        config = worldgen or defaults()
        payload = directory / (run_id + "-request.json")
        payload.write_text(
            json.dumps(
                {
                    "noise_settings": noise_settings(
                        template("noise_settings"), config
                    ),
                    "volume": volume,
                }
            ),
            encoding="utf-8",
        )
        command.append(str(payload.resolve()))
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with log.open("w", encoding="utf-8") as stream:
        process = subprocess.Popen(
            command,
            stdout=stream,
            stderr=subprocess.STDOUT,
            creationflags=flags,
            cwd=directory,
        )
        start = time.monotonic()
        previous = -1
        try:
            while process.poll() is None:
                if cancel.wait(0.15):
                    raise SampleCancelled()
                if time.monotonic() - start > 180:
                    raise RuntimeError(f"Terrain sampling timed out. Log: {log}")
                text = log.read_text(encoding="utf-8", errors="replace")
                rows = re.findall(r"BC_PROGRESS (\d+) (\d+)", text)
                if rows and int(rows[-1][0]) != previous:
                    previous = int(rows[-1][0])
                    progress(*map(int, rows[-1]))
            if cancel.is_set():
                raise SampleCancelled()
            if process.returncode or not output.exists():
                raise RuntimeError(
                    f"Minecraft terrain sampling failed. Log: {log}\n"
                    + log.read_text(encoding="utf-8", errors="replace")[-1800:]
                )
            data = validate_sample(json.loads(output.read_text()))
            actual = SampleRequest(
                int(data["seed"]),
                data["center_x"],
                data["center_z"],
                data["span"],
                data["grid"],
            )
            if actual != request:
                raise ValueError("Minecraft returned a sample for different settings.")
            if worldgen is not None:
                data["worldgen"] = worldgen
            progress(request.grid, request.grid)
            return data
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
