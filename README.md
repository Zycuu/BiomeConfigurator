# Biome Configurator Studio, Fabric 26.3

A GPL fork of aepplestan's Biome Configurator for Minecraft Java **26.3 Fabric**.
Version 0.3 adds an integrated world-generation workbench with block geometry,
editable landforms, noise caves, ore rules, and protected project export.

## Start and workflow

Open `BiomeConfiguratorFabric.exe`. Python is not required by the Windows build.
Choose your existing Fabric project and block PNG folder in **Fabric Project**.
The main editor handles material IDs/textures, biome tint, climate, atmosphere,
audio, mobs, and tree/plant counts. Open **Worldgen Studio** for terrain and caves.

1. Choose a landform in Terrain. Selecting one loads sensible starter parameters.
2. Enter a seed and X/Z position. Use Area 64/Grid 65 or Area 128/Grid 129 for
   **one-block sampling**. Larger area with the same grid is a coarser preview.
3. Click Generate Terrain. The previous sample stays usable while Minecraft
   samples the edited graph in a background process. Cancel stops that process.
4. Drag left to orbit, drag right to pan, and use the wheel to zoom. Surface,
   Half cutaway, and Horizontal slice inspect the same sampled solid blocks.
   Slice Y selects a horizontal block layer. Palette edits update colors live.
   Auto regenerate optionally resamples when generation settings change.
5. Add ore rules and feature options. Save Design retains the complete setup.
6. Review & Export to Fabric lists every file change before writing. Existing
   changed files receive backups. Reload Gradle, run Minecraft, and create a new
   `<Biome Name> Preview` world to check final terrain, materials, and features.

The block preview has horizontal tops and vertical sides, not sloping polygons.
It uses a voxel occupancy sample for underground noise caves and floating land.
At coarse spacing, columns represent multiple horizontal blocks. Palette colors
are derived from selected textures; this is not a full textured Minecraft renderer.

## Landforms

The studio includes Vanilla Overworld, Flatlands, Rolling Hills, Mountains,
Ridged Highlands, Plateaus, Dunes, Archipelago, Ocean Basins, Canyons, and Floating
Islands. Custom presets export real Minecraft density graphs, not viewing effects.
Controls include base elevation, relief amplitude, landform wavelength, detail,
sea level/fluid, plateau step height, and floating island thickness.

Relief amplitude is not an exact maximum peak height. Flatlands ignores relief
and detail. Floating islands use air instead of a sea. Water, lava, and air can
otherwise be selected. Save Image writes the displayed view as PNG.

Custom noise caves support None, Tunnels, Chambers, or Mixed, with density,
size multiplier, and vertical limits. Larger density opens more underground space.
Vanilla Overworld intentionally retains its stock density graph and noise caves;
select a custom landform to use the custom cave controls.

## What applies where

Terrain and noise caves are properties of a chunk generator, not just a biome.
Custom shape is installed into the dedicated Preview world preset. Normal
Overworld placement retains the Overworld's generator and carvers.

For custom landforms the exporter creates an internal `<biome>_studio` biome for
Preview worlds and optional new dimensions. It shares the design's palette and
features but omits vanilla carvers so extra tunnels do not bypass the selected
noise cave settings. Material rules apply to both biome variants.

The Export tab can also create a **new dimension** using this generator. Enter a
new lowercase path; the mod namespace is added automatically. It uses Overworld
dimension physics. It does not adopt Far Dark's existing clocks, sky rendering,
or lighting. Existing unmanaged dimension files are protected by preflight.
The tool never replaces the global Overworld dimension definition.

## Ores and features

Ore rules use an existing registered block ID, attempts per chunk, vein size,
minimum/maximum Y, uniform/triangle distribution, and air-exposure discard chance.
Use the dropdown for vanilla ores or type an ID already registered by your mod.
The tool does not create a new ore block from that ID. The chart illustrates the
vertical attempt distribution, not exact vein locations or guaranteed output.
Real ore features and placements are exported. The exporter extends the custom
stone replacement and 26.3 motion-blocking tags required by heightmaps.

Features provides tree/plant counts and switches for vanilla lava lakes, geodes,
monster rooms, and springs. The Ores tab separately controls the vanilla
underground feature set, which also contains stone patches and disks.

The viewport does not simulate placed ore veins, decorations, structures, final
surface-rule painting, vanilla carvers, or shaders. Tree markers only illustrate
density. Underground fluid volumes are not drawn. Always inspect a new Preview
world for the final result. Vanilla structures are not a structure-placement editor.

## Materials and project integration

Select PNGs in Materials for grass, dirt, two stones, short/tall plants, and two
log/leaf families. Tinted mode exports grayscale copies while preserving alpha;
untinted mode retains painted colors. Original textures and `.png.mcmeta` files
are preserved. Animated textures show their first frame in the palette preview.

Export installs Java block/item registration, client tint registration, models,
item definitions, loot, tags, language entries, biome/feature/material rules,
noise settings, a Preview world preset, and optional dimension data. It adds a
TerraBlender dependency and preserves existing initializer entries. TerraBlender
is included in the built mod JAR; Fabric API is a normal dependency.

Supported projects: single-project Groovy Fabric Loom templates for 26.3 with
shared or split client/main sources. Other versions/layouts are rejected rather
than guessed. New generated block IDs must not duplicate existing registrations.
Grass is static terrain; spreading, saplings, wood crafting, and custom ore
behavior remain mod-code work. Tree generators use vanilla oak shapes.

## Preservation

Opening the app and sampling terrain do not change a selected project. Export
checks conflicts and changes made after review. Edited generated files stop an
export. Every changed existing file is backed up under
`.biome-configurator-backups/<timestamp>/originals/`; interrupted new files are
preserved with the backup. `.biome-configurator.json` tracks designs and hashes.
Several biome designs can share a project. Shared block definitions must agree.
No worlds are deleted or regenerated. Legacy staging is archived, not deleted.
Use new test worlds after changing world generation.

## Runtime and source build

Fresh sampling needs Java 25 in JAVA_HOME or IntelliJ's `~/.jdks`, and a populated
Minecraft 26.3 Loom cache under GRADLE_USER_HOME or `~/.gradle`. Run the Fabric
26.3 development client once to populate it. The app runs our own Java bridge
against those cached vanilla libraries. It does not run selected mod code or
Gradle, start a server, or require a Minecraft login for sampling.

Logs and sample/request JSON are retained under
`%LOCALAPPDATA%/BiomeConfiguratorFabric/terrain-samples`. The bundled initial
sample uses seed 0, X/Z 0, a 64-block area, and a 65 by 65 grid. No Minecraft game
JARs, game classes, textures, sounds, or user artwork are included in the build.
The bridge JAR contains only our own GPL class; its source is in bridge/java.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe FabricBiomeConfigurator.py
.\.venv\Scripts\python.exe bridge/build_bridge.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tests/terrain_integration.py
```

Windows packaging:

```powershell
.\.venv\Scripts\python.exe -m pip install pyinstaller
.\.venv\Scripts\python.exe -m PyInstaller --onefile --windowed --name BiomeConfiguratorFabric --icon icon.ico --add-data "minecraft_26_3_templates.json;." --add-data "default_terrain_26_3.json;." --add-data "bridge/terrain-sampler-26.3.jar;bridge" FabricBiomeConfigurator.py
```

## Verification and references

26 automated tests cover export preservation, migration, geometry, cave/terrain
settings, ore resources, and camera controls. All 11 landform modes were decoded
and sampled by the installed Minecraft 26.3 engine. Real sampling confirmed that
higher cave density creates more empty voxels. The disposable Fabric integration
project passed biome/material loading, custom tree placement, custom ore placement
in Gloomstone, shared/client Java compilation, and mod JAR build. See
`tests/GAMETEST.md`. This does not replace an interactive Minecraft visual check.

Fabric's [dimension concepts](https://wiki.fabricmc.net/tutorial:dimensionconcepts)
describe the division between biome sources, generators, carvers, and surface
rules. [Feature generation](https://docs.fabricmc.net/develop/data-generation/features)
describes feature and placement concepts. Exact 26.3 JSON/API formats here were
checked against the locally installed game code and resources, then tested in
Minecraft. Custom landform presets are this tool's density graphs, not claims
that those named world types appear in vanilla's creation menu.

Original app: [aepplestan/BiomeConfigurator](https://github.com/aepplestan/BiomeConfigurator).
The fork retains GPL-3.0 and preserves `README.upstream.md`, LICENSE, and UPSTREAM.md.
