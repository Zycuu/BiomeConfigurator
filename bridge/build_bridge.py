"""Rebuild only our GPL Java bridge using the installed JDK and cached game dependencies."""
from pathlib import Path
import subprocess
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from terrain_sampler import discover_runtime


def main():
    java, libraries = discover_runtime()
    executable = ".exe" if java.suffix == ".exe" else ""
    classes = ROOT / "build" / ("terrain-classes-" + uuid.uuid4().hex[:8])
    classes.mkdir(parents=True)
    subprocess.run([str(java.with_name("javac" + executable)), "--release", "25", "-cp",
                    __import__("os").pathsep.join(map(str, libraries[1:])), "-d", str(classes),
                    str(ROOT / "bridge/java/terrainbridge/TerrainSampler.java")], check=True)
    jar = ROOT / "bridge/terrain-sampler-26.3.jar"
    subprocess.run([str(java.with_name("jar" + executable)), "--create", "--file", str(jar),
                    "-C", str(classes), "terrainbridge"], check=True)
    with zipfile.ZipFile(jar) as archive:
        assert all(name.startswith(("META-INF/", "terrainbridge/")) for name in archive.namelist())
    print("Built", jar)


if __name__ == "__main__":
    main()
