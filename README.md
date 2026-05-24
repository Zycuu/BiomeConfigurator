# Biome Configurator v1.0

A lightweight, visual desktop application for designing, previewing, and exporting custom Minecraft biomes. Perfect for integrating with tools like WorldPainter or creating standalone dimension datapacks! Tested on Minecraft versions 1.21 up to the latest 26.1 release.

## Features

* **Live 3D Preview**: See your biome's atmosphere, foliage colors, weather, and ambient particles update in real-time on an isometric 3D chunk.
* **Atmosphere & Climate**: Customize sky, fog, water, and grass colors using a built-in color picker. Adjust temperature, downfall, and snow thresholds.
* **Mob Spawns**: Easily configure spawn weights, pack sizes, and mob caps (energy budgets/charges) for any vanilla entity.
* **Ambience**: Add immersive particles (like ash or falling spores) and ambient sound loops/moods.
* **1-Click Datapack Generation**: Stage multiple biomes and instantly bundle them into a ready-to-use Minecraft Datapack.

## Download & Install (For Users)

The easiest way to use the Biome Configurator is to download the standalone executable:

1. Go to the [Releases](../../releases) tab on the right side of this page.
2. Download the latest `BiomeConfigurator.exe` file.
3. Double-click to run the program (no installation required!).

## How to Use
1. Start with a vanilla biome template from the top dropdown.
2. Adjust colors, weather, and mobs across the 4 tabs. Live preview is fairly accurate to appearance in-game. *(Note: Grass modifiers apply colored noise patterns to biome grass and will overwrite the standard color selection for grass).*
3. Enter a custom Biome ID (e.g., `New_Forest`) at the bottom and click **Export Biome JSON**. You can do this multiple times for different biomes.
4. Once you've exported your biomes, click **Generate Datapack** to bundle them all into a folder ready to be dropped into your Minecraft world.
5. Open WorldPainter, click **Add Custom Biome** in the layers tab, and name the biome `custom:[biome_name]` (e.g., `custom:New_Forest`).
6. Apply the biome layer as you wish, then export the map. Once exported, move the newly generated datapack to your map's datapacks folder.

## Troubleshooting & Known Issues

* **Minecraft refuses to load the datapack**: Sometimes old or conflicting data gets stuck in the staging folder. If this happens, click **Clear Staging** in the app and generate a new datapack from scratch.
* **Mob Spawns**: You can expect mob spawns to sometimes give you difficulty by nature of WorldPainter exports, but they should all function appropriately as configured through this script.
