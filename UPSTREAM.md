# Upstream and changes

This is a modified edition of [aepplestan/BiomeConfigurator](https://github.com/aepplestan/BiomeConfigurator).

- Upstream commit: `9addffed3771919efc8888dbb4334227691d33b2`.
- Upstream license: GPL-3.0, preserved in `LICENSE`.
- Original documentation: `README.upstream.md`.
- Fabric extension date: October 23, 2026.

The original app remains in `BiomeConfigurator.py`; its rendering loop now calls
a small overridable `draw_scene` method. The Fabric entrypoint, project inspector,
content exporter, Java templates, tests, and new UI are separate files.

`minecraft_26_3_templates.json` contains reference world-generation definitions
and a grass model obtained from the installed Minecraft Java 26.3 distribution.
It contains no texture images, sounds, game classes, or user artwork. The exporter
uses these definitions to preserve the exact 26.3 registry format.

TerraBlender's 26.3 API and dependency coordinates were checked against the
official [Glitchfiend/TerraBlender](https://github.com/Glitchfiend/TerraBlender/tree/26.3)
source and its Maven repository. The app's preview is illustrative; Minecraft is
the authoritative renderer and generator.

The v0.2 terrain viewer is implemented in `terrain_ui.py`, `terrain_renderer.py`,
and `terrain_sampler.py`. The GPL source and compiled class for our bridge are in
`bridge/`. The bridge loads existing Minecraft 26.3 libraries locally and reads
server-data tags before sampling Overworld base heights. The bundled default JSON
is numeric output from that sampler, not a copy of Minecraft code or artwork.
The interactive renderer and illustrative tree markers are our own implementation.
