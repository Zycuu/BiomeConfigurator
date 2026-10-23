"""Opt-in real Minecraft/JDK integration check. Does not start a game or touch a project."""

from pathlib import Path
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from terrain_sampler import SampleRequest, sample_terrain


def main():
    output = Path(tempfile.mkdtemp(prefix="bc-terrain-integration-"))
    bundled = json.loads((ROOT / "default_terrain_26_3.json").read_text())
    from worldgen_studio import defaults

    request = SampleRequest(grid=bundled["grid"], span=bundled["span"])
    baseline = sample_terrain(request, output, worldgen=defaults(), volume=True)
    assert (
        baseline == bundled
    ), "The installed engine no longer reproduces the bundled sample"
    other_seed = sample_terrain(
        SampleRequest(seed=42, grid=request.grid, span=request.span), output
    )
    assert (
        baseline["heights"] != other_seed["heights"]
    ), "Different seeds produced identical terrain"
    adjacent = sample_terrain(
        SampleRequest(center_x=request.span, grid=request.grid, span=request.span),
        output,
    )
    assert [row[-1] for row in baseline["heights"]] == [
        row[0] for row in adjacent["heights"]
    ], "Adjacent samples do not meet at the same world coordinates"
    assert baseline["max_height"] > baseline["min_height"] > -64
    print(
        "PASS: bundled seed reproduction, different-seed variation, and seamless adjacent coordinates."
    )
    print("Samples and logs preserved at", output)


if __name__ == "__main__":
    main()
