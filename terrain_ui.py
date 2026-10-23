"""Orbitable, asynchronous Minecraft terrain preview for the Fabric editor."""
import json
import os
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

from fabric_support import texture_image, is_tinted
from terrain_sampler import SampleRequest, SampleCancelled, minecraft_seed, sample_terrain, validate_sample
from terrain_renderer import TerrainRenderer, rgb


class TerrainWindow:
    def __init__(self, app):
        self.app = app
        self.window = tk.Toplevel(app.root)
        self.window.title("Minecraft Terrain Visualizer - Biome Configurator Fabric")
        self.window.geometry("1260x850")
        self.window.minsize(1120,650)
        self.renderer = TerrainRenderer()
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.worker = None
        self.pending = None
        self.poll_id = None
        self.traces = []
        self.sample = validate_sample(json.loads(Path(__file__).with_name("default_terrain_26_3.json").read_text()))
        self.seed = tk.StringVar(value=self.sample["seed"])
        self.x = tk.StringVar(value=str(self.sample["center_x"]))
        self.z = tk.StringVar(value=str(self.sample["center_z"]))
        self.span = tk.StringVar(value=str(self.sample["span"]))
        self.detail = tk.StringVar(value=str(self.sample["grid"]))
        self.water = tk.BooleanVar(value=True)
        self.trees = tk.BooleanVar(value=True)
        self.wire = tk.BooleanVar(value=False)
        self.exaggeration = tk.DoubleVar(value=1)
        self.status = tk.StringVar(value="Bundled Minecraft sample. Change the seed or position and click Generate Terrain.")
        self.info = tk.StringVar()
        self.build_layout()
        self.update_sample_info()
        variables = [self.water,self.trees,self.wire,self.exaggeration,app.tint_grass,app.tint_leaves,
                     *app.colors.values(),*app.texture_vars.values(),*app.generation.values(),app.texture_dir]
        for variable in variables:
            token = variable.trace_add("write",self.request_render)
            self.traces.append((variable,token))
        self.window.protocol("WM_DELETE_WINDOW",self.close)
        self.window.bind("<Destroy>",self.on_destroy,add=True)
        self.poll_id = self.window.after(100,self.poll)
        self.request_render()

    def on_destroy(self,event):
        if event.widget is self.window:
            self.cancel.set()

    def build_layout(self):
        top = ttk.Frame(self.window,padding=10)
        top.pack(fill="x")
        for label,variable,width in [("Seed",self.seed,19),("Center X",self.x,9),("Z",self.z,9)]:
            ttk.Label(top,text=label).pack(side="left",padx=(7,3))
            ttk.Entry(top,textvariable=variable,width=width).pack(side="left")
        for label,variable,values in [("Area",self.span,(128,256,512,1024,2048)),("Grid",self.detail,(33,65,129))]:
            ttk.Label(top,text=label).pack(side="left",padx=(9,3))
            ttk.Combobox(top,textvariable=variable,values=values,width=6,state="readonly").pack(side="left")
        self.generate_button = ttk.Button(top,text="Generate Terrain",command=self.generate)
        self.generate_button.pack(side="left",padx=10)
        self.cancel_button = ttk.Button(top,text="Cancel",command=self.cancel.set,state="disabled")
        self.cancel_button.pack(side="left")
        toolbar = ttk.Frame(self.window,padding=(10,0,10,7))
        toolbar.pack(fill="x")
        for label,variable in [("Water",self.water),("Tree markers (illustrative)",self.trees),("Mesh",self.wire)]:
            ttk.Checkbutton(toolbar,text=label,variable=variable).pack(side="left",padx=5)
        ttk.Button(toolbar,text="Reset View",command=self.reset).pack(side="left",padx=5)
        ttk.Button(toolbar,text="Top View",command=self.top_view).pack(side="left",padx=5)
        ttk.Button(toolbar,text="Save Image...",command=self.save_image).pack(side="left",padx=5)
        ttk.Label(toolbar,text="Height scale:").pack(side="left",padx=(12,0))
        ttk.Scale(toolbar,from_=.5,to=3,variable=self.exaggeration,length=120).pack(side="left",padx=5)
        ttk.Label(self.window,textvariable=self.info,padding=(16,3)).pack(fill="x")
        self.canvas = tk.Canvas(self.window,background="#121b24",highlightthickness=0)
        self.canvas.pack(fill="both",expand=True,padx=10)
        self.canvas.bind("<Configure>",self.request_render)
        self.canvas.bind("<ButtonPress-1>",self.start_drag)
        self.canvas.bind("<B1-Motion>",self.orbit)
        self.canvas.bind("<ButtonPress-3>",self.start_drag)
        self.canvas.bind("<B3-Motion>",self.pan)
        self.canvas.bind("<MouseWheel>",self.zoom)
        self.canvas.bind("<Button-4>",lambda event:self.zoom(event,1))
        self.canvas.bind("<Button-5>",lambda event:self.zoom(event,-1))
        self.progress = ttk.Progressbar(self.window,maximum=100)
        self.progress.pack(fill="x",padx=10,pady=(5,0))
        ttk.Label(self.window,textvariable=self.status,padding=(16,4),wraplength=1180).pack(fill="x")
        ttk.Label(self.window,text="Left drag: orbit   |   Right drag: pan   |   Wheel: zoom   |   Palette changes update live",
                  padding=(16,2)).pack(fill="x")
        ttk.Label(self.window,text="Base terrain heightfield, not a full chunk render. Caves, overhangs, structures, biome borders and exact feature placement are omitted.\nArea and seed select a preview location; they do not change exported world generation. Height scale is a viewing aid.",
                  padding=(16,2),wraplength=1180).pack(fill="x")

    def update_sample_info(self):
        s=self.sample
        self.info.set(f"Displaying seed {s['seed']}  |  X {s['center_x']}, Z {s['center_z']}  |  {s['span']} x {s['span']} blocks  |  samples every {s['step']} blocks")

    def start_drag(self,event):
        self.drag = (event.x,event.y)

    def orbit(self,event):
        oldx,oldy=getattr(self,"drag",(event.x,event.y))
        self.renderer.yaw += (event.x-oldx)*.008
        self.renderer.pitch = max(.08,min(1.56,self.renderer.pitch+(event.y-oldy)*.006))
        self.drag=(event.x,event.y)
        self.request_render()

    def pan(self,event):
        oldx,oldy=getattr(self,"drag",(event.x,event.y))
        self.renderer.pan_x += event.x-oldx
        self.renderer.pan_y += event.y-oldy
        self.drag=(event.x,event.y)
        self.request_render()

    def zoom(self,event,direction=None):
        direction = direction if direction is not None else (1 if event.delta>0 else -1)
        self.renderer.zoom=max(.2,min(10,self.renderer.zoom*(1.15 if direction>0 else 1/1.15)))
        self.request_render()

    def reset(self):
        self.renderer.reset()
        self.exaggeration.set(1)
        self.request_render()

    def top_view(self):
        self.renderer.pitch=1.56
        self.renderer.yaw=0
        self.request_render()

    def palette(self):
        design=self.app.gather_design()
        colors=design["colors"]
        result={"grass":rgb(colors["grass_color"]),"water":rgb(colors["water_color"]),
                "tree1_leaves":rgb(colors["foliage_color"]),"tree2_leaves":rgb(colors["foliage_color"]),
                "tree1_count":design["tree1_count"],"tree2_count":design["tree2_count"]}
        if self.app.texture_dir.get():
            for role in ("grass_top","dirt","stone","tree1_leaves","tree2_leaves","tree1_log","tree2_log"):
                image=texture_image(design,role,preview=True)
                if is_tinted(design,role):
                    image=self.app.apply_color(image,colors["foliage_color" if role.endswith("_leaves") else "grass_color"])
                visible=[pixel[:3] for pixel in image.convert("RGBA").getdata() if pixel[3]>100]
                if visible:
                    result["grass" if role=="grass_top" else role]=tuple(round(sum(p[i] for p in visible)/len(visible)) for i in range(3))
                if role=="grass_top":
                    result["grass_pixels"]=list(image.convert("RGB").resize((16,16),Image.Resampling.NEAREST).getdata())
        return result

    def request_render(self,*args):
        if self.pending is None and self.window.winfo_exists():
            self.pending=self.window.after(35,self.render)

    def render(self):
        self.pending=None
        try:
            palette=self.palette()
            self.renderer.vertical=self.exaggeration.get()
            self.last_image=self.renderer.render(self.sample,(self.canvas.winfo_width(),self.canvas.winfo_height()),palette,
                                                 self.water.get(),self.trees.get(),self.wire.get())
            self.photo=ImageTk.PhotoImage(self.last_image,master=self.window)
            self.canvas.delete("terrain")
            self.canvas.create_image(0,0,image=self.photo,anchor="nw",tags="terrain")
        except (ValueError,OSError,KeyError) as error:
            self.status.set(f"Finish the palette/settings to update the terrain colors: {error}")

    def generate(self):
        if self.worker and self.worker.is_alive():
            return
        try:
            request=SampleRequest(minecraft_seed(self.seed.get()),int(self.x.get()),int(self.z.get()),int(self.span.get()),int(self.detail.get())).validate()
        except ValueError as error:
            messagebox.showerror("Terrain settings",str(error),parent=self.window)
            return
        self.cancel=threading.Event()
        self.generate_button.config(state="disabled")
        self.cancel_button.config(state="normal")
        self.progress["value"]=0
        self.status.set("Starting Minecraft 26.3 terrain generation. The displayed sample stays available while this runs.")
        folder=Path(os.environ.get("LOCALAPPDATA",Path.home()))/"BiomeConfiguratorFabric/terrain-samples"
        def work():
            try:
                data=sample_terrain(request,folder,lambda row,total:self.events.put(("progress",(row,total))),self.cancel)
                self.events.put(("done",data))
            except SampleCancelled:
                self.events.put(("cancelled",None))
            except Exception as error:
                self.events.put(("error",str(error)))
        self.worker=threading.Thread(target=work,daemon=False)
        self.worker.start()

    def poll(self):
        while True:
            try:
                kind,value=self.events.get_nowait()
            except queue.Empty:
                break
            if kind=="progress":
                self.progress["value"]=100*value[0]/value[1]
                self.status.set(f"Sampling Minecraft terrain: row {value[0]} of {value[1]}...")
            else:
                self.generate_button.config(state="normal")
                self.cancel_button.config(state="disabled")
                if kind=="done":
                    self.sample=value
                    self.update_sample_info()
                    self.progress["value"]=100
                    self.status.set("Minecraft terrain ready. Orbit, zoom, or change your biome palette. Tree markers are illustrative.")
                    self.request_render()
                elif kind=="cancelled":
                    self.status.set("Sampling cancelled. The previous sample is still displayed.")
                else:
                    self.status.set("Sampling could not finish. The previous sample is still displayed.")
                    messagebox.showerror("Terrain sampler",value,parent=self.window)
        self.poll_id=self.window.after(100,self.poll)

    def save_image(self):
        path=filedialog.asksaveasfilename(parent=self.window,title="Save terrain preview image",defaultextension=".png",filetypes=[("PNG image","*.png")])
        if path and hasattr(self,"last_image"):
            self.last_image.save(path)

    def close(self):
        self.cancel.set()
        for variable,token in self.traces:
            variable.trace_remove("write",token)
        if self.pending:
            self.window.after_cancel(self.pending)
        if self.poll_id:
            self.window.after_cancel(self.poll_id)
        self.window.destroy()
        self.app.terrain_window=None
