"""Small CPU heightfield renderer. Samples are real terrain; vegetation is illustrative."""
import math
import random
from PIL import Image, ImageDraw


def rgb(value):
    return tuple(bytes.fromhex(value.lstrip("#")))


def shade(color, amount):
    return tuple(max(0, min(255, round(channel * amount))) for channel in color[:3])


def clip_water(vertices, level):
    result = []
    for current, following in zip(vertices, vertices[1:] + vertices[:1]):
        inside, next_inside = current[1] <= level, following[1] <= level
        if inside:
            result.append((current[0], level, current[2]))
        if inside != next_inside:
            ratio = (level - current[1]) / (following[1] - current[1])
            result.append((current[0] + ratio * (following[0] - current[0]), level,
                           current[2] + ratio * (following[2] - current[2])))
    return result


class TerrainRenderer:
    def __init__(self):
        self.yaw = -.72
        self.pitch = .62
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0
        self.vertical = 1.0

    def reset(self):
        self.__init__()

    def render(self, sample, size, palette, water=True, trees=True, wire=False):
        width, height = max(100, size[0]), max(100, size[1])
        image = Image.new("RGB", (width, height), "#121b24")
        draw = ImageDraw.Draw(image)
        for y in range(height):
            t = y / height
            draw.line((0, y, width, y), fill=(round(18 + 15*t), round(27 + 17*t), round(36 + 18*t)))
        n, span, heights = sample["grid"], sample["span"], sample["heights"]
        step, sea = sample["step"], sample["sea_level"]
        mid = (sample["min_height"] + max(sea, sample["max_height"])) / 2
        scale = min(width * .65, height * .95) / span * self.zoom
        cy, sy, cp, sp = math.cos(self.yaw), math.sin(self.yaw), math.cos(self.pitch), math.sin(self.pitch)

        def project(point):
            x, elevation, z = point
            horizontal = cy*x - sy*z
            away = sy*x + cy*z
            y = (elevation - mid) * self.vertical
            return (width/2 + self.pan_x + horizontal*scale,
                    height*.49 + self.pan_y + (away*sp - y*cp)*scale,
                    -away*cp - y*sp)

        grass = palette.get("grass", (88, 114, 78))
        stone = palette.get("stone", (90, 94, 100))
        dirt = palette.get("dirt", (96, 78, 66))
        water_color = palette.get("water", (43, 97, 135))
        faces = []

        def face(vertices, color, outline=None):
            points = [project(point) for point in vertices]
            faces.append((sum(p[2] for p in points)/len(points), [(p[0], p[1]) for p in points], color, outline))

        base = sample["min_height"] - 18
        # Solid cutaway skirts make the sampled region read as a terrain slice.
        for i in range(n-1):
            p = -span/2 + i*step
            for a, b in [((p, heights[0][i], -span/2), (p+step, heights[0][i+1], -span/2)),
                         ((p, heights[-1][i], span/2), (p+step, heights[-1][i+1], span/2)),
                         ((-span/2, heights[i][0], p), (-span/2, heights[i+1][0], p+step)),
                         ((span/2, heights[i][-1], p), (span/2, heights[i+1][-1], p+step))]:
                face([a, b, (b[0], base, b[2]), (a[0], base, a[2])], shade(stone, .52))
                face([a, b, (b[0], b[1]-3, b[2]), (a[0], a[1]-3, a[2])], shade(dirt, .68))
        pattern = palette.get("grass_pixels")
        for z in range(n-1):
            for x in range(n-1):
                px, pz = x*step-span/2, z*step-span/2
                h00, h10 = heights[z][x], heights[z][x+1]
                h01, h11 = heights[z+1][x], heights[z+1][x+1]
                points = [(px,h00,pz),(px+step,h10,pz),(px+step,h11,pz+step),(px,h01,pz+step)]
                dx = ((h10+h11)-(h00+h01))/(2*step)
                dz = ((h01+h11)-(h00+h10))/(2*step)
                slope = math.hypot(dx,dz)
                normal = math.sqrt(dx*dx+dz*dz+1)
                light = .55 + .48*max(0, (-dx*(-.5)+.8-dz*(-.3))/normal)
                color = stone if slope > 1.3 else grass
                if pattern and slope <= 1.3:
                    color = pattern[(z % 16)*16+(x % 16)]
                if sum((h00,h10,h01,h11))/4 < sea-1:
                    color = shade(dirt,.82)
                face(points, shade(color,light), shade(color,.60) if wire else None)
                if water and min(h00,h10,h01,h11) < sea:
                    for triangle in ([points[0],points[1],points[2]], [points[0],points[2],points[3]]):
                        polygon = clip_water(triangle,sea+.08)
                        if len(polygon)>=3:
                            face(polygon, shade(water_color,.90+((x+z)%5)*.015))
        if trees:
            rng = random.Random(int(sample["seed"]) ^ sample["center_x"] ^ (sample["center_z"] << 1))
            # Markers are deliberately bounded and not presented as Minecraft feature placements.
            first, second = palette.get("tree1_count",3), palette.get("tree2_count",2)
            count = min(500, round((first+second)*span*span/256*.13))
            for _ in range(count):
                x,z = rng.randrange(1,n-1),rng.randrange(1,n-1)
                h = heights[z][x]
                if h<=sea or abs(h-heights[z][x+1])+abs(h-heights[z+1][x]) > step*1.5:
                    continue
                kind = "tree1" if rng.random() < first/max(1,first+second) else "tree2"
                leaf = palette.get(kind+"_leaves",(63,99,68))
                bark = palette.get(kind+"_log",(73,59,45))
                # Small 3D crown and trunk, sorted with terrain for occlusion.
                tx,tz = x*step-span/2,z*step-span/2
                trunk_h = 5+rng.randrange(3)
                r = 2.1
                face([(tx-.45,h,tz),(tx+.45,h,tz),(tx+.45,h+trunk_h,tz),(tx-.45,h+trunk_h,tz)],bark)
                y=h+trunk_h
                face([(tx-r,y,tz-r),(tx+r,y,tz-r),(tx+r,y,tz+r),(tx-r,y,tz+r)],shade(leaf,.78))
                face([(tx-r,y,tz-r),(tx+r,y,tz-r),(tx+r,y+3,tz-r),(tx-r,y+3,tz-r)],shade(leaf,.72))
                face([(tx-r,y,tz+r),(tx+r,y,tz+r),(tx+r,y+3,tz+r),(tx-r,y+3,tz+r)],shade(leaf,.86))
                face([(tx-r,y+3,tz-r),(tx+r,y+3,tz-r),(tx+r,y+3,tz+r),(tx-r,y+3,tz+r)],leaf)
        for _, polygon, color, outline in sorted(faces, key=lambda item:item[0], reverse=True):
            draw.polygon(polygon,fill=color,outline=outline)
        # Scale, coordinates, and key remain readable independently of the camera.
        draw.rounded_rectangle((16,16,385,83),radius=8,fill="#15212d",outline="#344556")
        draw.text((28,26),f"MINECRAFT 26.3  /  BASE TERRAIN",fill="#b8d7e3")
        draw.text((28,45),f"{span} x {span} blocks  |  Y {sample['min_height']} to {sample['max_height']}",fill="#e0e9ec")
        draw.text((28,63),f"X {sample['center_x']}  Z {sample['center_z']}  |  Sea level {sea}",fill="#aab9c1")
        return image
