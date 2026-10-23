# Minecraft integration check

`java/GeneratedBiomeGameTest.java` targets a disposable export with namespace
`far_dark`, biome `gloam_woods`, and the starter palette. Do not install the test
classes or test entrypoint into your production mod.

1. Copy a Minecraft 26.3 Fabric template into a separate test project.
2. Export the starter design there with a custom landform, plus an ore rule named
   `studio_diamond` using `minecraft:diamond_ore`, size 16, and discard chance 0.
   Use the app or `build_plan(...).apply()`.
3. Add `tests/java` as a temporary main Java source directory in that copy.
4. In the test copy's processed `fabric.mod.json`, add a `fabric-gametest`
   entrypoint containing `validation.GeneratedBiomeGameTest`.
5. Configure the Loom server run with `-Dfabric-api.gametest=true` and optionally
   `-Dfabric-api.gametest.report-file=<absolute report path>`.
6. Run the Loom `runServer` task using JDK 25.

Fabric's GameTest server runs headlessly without accepting a dedicated server
EULA on your behalf. The custom test checks biome registration, the parsed
material rule and preview noise settings, and actual custom tree placement on
Ash Dirt. It does not claim to validate client rendering or full terrain appearance.

The v0.3 ore test fills a region with custom Gloomstone and checks that the exported
ore feature replaces it with diamond ore. The exporter must extend the 26.3
`minecraft:blocks_motion` tag as well as ore replacement tags.
