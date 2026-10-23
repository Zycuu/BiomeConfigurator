# Biome Configurator Fabric

A modified edition of **aepplestan's Biome Configurator**, focused on selecting
custom textures, previewing a biome palette, and installing generated content into
an existing **Minecraft Java 26.3 Fabric** project.

## Start

Windows: open `BiomeConfiguratorFabric.exe` from the packaged build. Python is not
required for that build. No mod project is changed merely by opening the app.

From source:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe FabricBiomeConfigurator.py
```

App presets and crash reports are stored in `%LOCALAPPDATA%\BiomeConfiguratorFabric`.

## Workflow

1. In **Fabric Project**, select the folder containing `build.gradle`,
   `gradle.properties`, and `src/main/resources/fabric.mod.json`.
2. Choose the folder containing your block PNG textures. The starter palette uses
   Duskgrass, Ash Dirt, Gloomstone, Deepstone, Gloom Oak, and Ashwood filenames.
   Select different files and block IDs in **Materials** as needed.
3. Select whether grass/plants and leaves use their painted colors or biome tint.
   Tint mode exports grayscale copies with preserved alpha. Original PNGs and
   matching `.png.mcmeta` files are preserved.
4. Set tree attempts, ground cover, stone transition height, placement template,
   and region weight in **Generation**. Adjust atmosphere, climate, and mobs in
   the existing tabs. No selected mobs means no natural biome mob spawns.
5. Give the biome a lowercase name, such as `gloam_woods`.
6. Click **Review & Export to Fabric**. Read the list, then choose
   **Export with Backups** to apply it.
7. Reload Gradle in IntelliJ and launch Minecraft. The first sync downloads
   TerraBlender and Fabric API from their Maven repositories.
8. Create a **new world**. Choose `<Biome Name> Preview` as the world type to see
   only this biome, or use Default for natural placement in the Overworld.
   Generated blocks are available in the Natural Blocks creative tab and `/give`.

Use **Save Design** to retain the full palette/settings outside the project.
**Load Last Project Design** reopens the last installed design. Several biomes
can be exported into one project. Shared block IDs must have identical definitions.
Create a unique ID when a material's texture or behavior differs between biomes.

## Dynamic terrain visualizer (v0.2)

Click **Open Minecraft Terrain Visualizer** below the palette preview. A bundled
seed-0 sample appears immediately. For another landscape, enter a numeric or text
seed, center X/Z, area size, and grid detail, then click **Generate Terrain**.
The current landscape remains usable while sampling. **Cancel** stops the sampler.

- Left drag orbits, right drag pans, and the wheel zooms. Reset and Top View help
  inspect terrain. Water, mesh, and illustrative tree markers can be toggled.
- Material selections and biome colors update the landscape live. The surface
  uses sampled texture colors; this is not a full textured voxel renderer.
- Height scale changes only the view. Exported generation stays at normal scale.
- Save Image exports the displayed terrain to PNG.
- New samples require **Java 25** in `JAVA_HOME` or IntelliJ's `~/.jdks`, plus the
  normal Minecraft 26.3 Loom cache under `GRADLE_USER_HOME` or `~/.gradle`.
  Run your 26.3 development client once to populate that cache. No extra mod,
  Minecraft login, Python installation, or running game is needed by the EXE.
- The sampler calls Minecraft's own `NoiseBasedChunkGenerator.getBaseHeight`
  with vanilla Overworld noise settings. Samples show ocean-floor base heights
  and sea-level water across the chosen area, independent of the palette.
- This is a heightfield, not complete generated chunks. Caves, overhangs,
  structures, exact trees/plants, surface-rule details, and biome borders are
  omitted. Tree markers illustrate relative density, capped at 500 for speed.
  Check the exported Preview world in Minecraft for authoritative results.
- Seed, position, area, and view controls are preview settings only. They do not
  export a terrain generator or fix the seed of a player's world. A biome alone
  does not define terrain shape. Current exports retain normal Overworld terrain.
- Logs and generated sample JSON are retained in
  `%LOCALAPPDATA%\BiomeConfiguratorFabric\terrain-samples`. Source textures,
  project files, and Minecraft saves are not touched by sampling.

The bundled sample is generated from seed 0 at X/Z 0, spanning 256 blocks with
65 x 65 samples. No Minecraft classes, game JARs, textures, or user artwork are
bundled. `bridge/java` contains the full source of our small GPL Java bridge.
Rebuild it with `python bridge/build_bridge.py` using an installed JDK 25 and
populated 26.3 cache. The included bridge JAR contains only our own class.

## What export installs

- Java block/item registration and client biome tint registration.
- Two generated log/leaves families with oak-shaped tree features.
- Grass terrain, dirt, two stones, two short plants, and a double-height plant.
- Block states, models, item definitions, loot tables, mining/soil/log/leaf tags,
  English names, textures, and texture metadata.
- Minecraft 26.3 biome JSON using the current environment-attribute spawn format.
- Tree and plant features and their placement settings.
- Material rules for the custom surface, subsoil, stone, and deep stone.
- TerraBlender region integration so the biome appears naturally in new
  Overworld generation. It uses a regional vanilla-biome overlay rather than
  replacing the whole Overworld dimension definition.
- A separate single-biome Preview world type.
- `biome-configurator.gradle` and one apply line in `build.gradle`.
  TerraBlender 26.3.0.0.9 is included in the built mod JAR. Fabric API remains a
  normal mod dependency. Existing initializer entries are retained.

## Preservation and recovery

The exporter preflights all changes. Conflicting unmanaged files, edited generated
files, and changes made after review stop the export. Every changed existing file
is copied under `.biome-configurator-backups/<timestamp>/originals/` before writes.
`changes.json` records the affected paths. A failed write restores originals and
preserves partially written new files under the same backup folder.

`.biome-configurator.json` records designs and hashes of generated files. Keep it
with the project. The app never deletes worlds or regenerates existing chunks.
It never executes selected project code or Gradle. The terrain sampler starts your
installed Java 25 with our bridge and your cached vanilla Minecraft libraries.
It does not run your mod, start a server, or open/save a world.
Legacy staging is archived rather than deleted.

## Current scope and limits

- Minecraft **26.3**, a single-project Groovy `build.gradle` Fabric Loom template,
  with either shared or split client/main sources. Other versions, Kotlin build
  scripts, and multi-module layouts are rejected rather than guessed.
- New block IDs only. This version does not adopt blocks you already registered
  elsewhere in Java. Choose distinct IDs to prevent duplicate registrations.
- The small palette scene is illustrative. The separate Terrain Visualizer samples
  actual vanilla 26.3 base terrain heights, then applies an approximate palette.
  Neither preview reproduces Minecraft rendering, shaders, or lighting. Animated
  textures show their first frame; tree markers do not use actual feature placement.
- Grass terrain is static. Grass spreading, saplings, bonemeal growth, stripped
  logs, planks, wood crafting, special ore behavior, and custom tree shapes are
  outside this first version.
- Basic self-drop loot is generated. Leaf sapling/shears behavior and plant loot
  balancing are future work.
- Worldgen changes affect new chunks/worlds. Always test in a new world first.
- The default Preview world changes neither the normal Overworld nor Far Dark's
  existing dimension. Natural generation uses TerraBlender's region weighting;
  region weight is not a percentage of total world coverage.

## Checks

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The export has also been tested against a disposable copy of a 26.3 Fabric
project: shared/client Java compilation, built JAR dependency inclusion, and a
Fabric headless GameTest loading the biome/material data and generating a custom
tree on custom dirt. The 20 automated tests cover export preservation, the palette, camera controls,
water clipping, sample validation, and sampler cancellation. A packaged-app smoke
test also generated seed-42 terrain and loaded all custom materials. Run
`python tests/terrain_integration.py` for an opt-in check using your installed
Minecraft cache: bundled seed reproduction, seed variation, and matching adjacent
sample edges. This does not start Minecraft or modify a mod project.
An interactive Minecraft client visual review is still recommended.

See `tests/GAMETEST.md` for integration-test setup and `UPSTREAM.md` for provenance.

## Build the Windows app

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name BiomeConfiguratorFabric --icon icon.ico --add-data "minecraft_26_3_templates.json;." --add-data "default_terrain_26_3.json;." --add-data "bridge/terrain-sampler-26.3.jar;bridge" FabricBiomeConfigurator.py
```

## Credits and license

Original application: [aepplestan/BiomeConfigurator](https://github.com/aepplestan/BiomeConfigurator).
This modified tool retains its GPL-3.0 license. The original README is preserved
as `README.upstream.md`. User textures are not included in the app or source archive.
