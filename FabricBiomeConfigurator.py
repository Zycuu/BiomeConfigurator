"""Launch the Fabric edition without writing beside the executable."""
import argparse
import os
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
import traceback
import json


def main():
    parser = argparse.ArgumentParser(description="Biome Configurator Fabric 26.3")
    parser.add_argument("--project", help="Existing Fabric project folder")
    parser.add_argument("--textures", help="Folder containing block PNG textures")
    parser.add_argument("--smoke-report", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-terrain", action="store_true", help=argparse.SUPPRESS)
    options = parser.parse_args()
    data_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "BiomeConfiguratorFabric"
    data_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(data_dir)
    root = tk.Tk()
    if options.smoke_report:
        root.withdraw()
    try:
        from fabric_app import FabricBiomeConfiguratorApp
        app = FabricBiomeConfiguratorApp(root)
        if options.project: app.set_project(options.project)
        if options.textures: app.set_texture_folder(options.textures)
        if options.smoke_report:
            root.update()
            app.refresh_palette()
            root.update()
            report = {"ready": True, "preview": app.preview_status.get(), "materials": sorted(app.cached_blocks)}
            if options.smoke_terrain:
                from terrain_sampler import SampleRequest, sample_terrain
                app.open_terrain()
                root.update()
                view = app.terrain_window
                view.render()
                from worldgen_studio import preset
                sample = sample_terrain(SampleRequest(seed=42, span=32, grid=33), data_dir / "terrain-samples", worldgen=preset("Canyons"), volume=True)
                view.sample = sample
                view.render()
                image_path = Path(options.smoke_report).with_suffix(".png")
                view.last_image.save(image_path)
                report["terrain"] = {"seed": sample["seed"], "min_height": sample["min_height"], "max_height": sample["max_height"], "image": str(image_path), "landform": sample["worldgen"]["terrain"], "voxel_columns": len(sample["columns"])}
                view.close()
            Path(options.smoke_report).write_text(json.dumps(report, indent=2), encoding="utf-8")
            root.destroy()
            return 0
        root.mainloop()
        return 0
    except Exception:
        report = traceback.format_exc()
        (data_dir / "crash_report.txt").write_text(report, encoding="utf-8")
        messagebox.showerror("Biome Configurator Fabric", f"The app could not start.\n\n{report}")
        root.destroy()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
