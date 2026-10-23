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
            result.append(
                (
                    current[0] + ratio * (following[0] - current[0]),
                    level,
                    current[2] + ratio * (following[2] - current[2]),
                )
            )
    return result


def occupied_columns(sample):
    import base64

    if "columns" in sample:
        return [
            [int.from_bytes(base64.b64decode(value), "little") for value in row]
            for row in sample["columns"]
        ]
    return [[(1 << max(0, h + 64)) - 1 for h in row] for row in sample["heights"]]


def bit_runs(bits):
    while bits:
        start = (bits & -bits).bit_length() - 1
        remaining = bits >> start
        length = (remaining ^ (remaining + 1)).bit_length() - 1
        end = start + length
        yield start, end
        bits &= ~(((1 << length) - 1) << start)


def voxel_mesh(sample, y_limit=320, cut=1.0, floor_y=-64):
    """Expose axis-aligned voxel faces. Vertical runs are merged without changing the surface."""
    columns = occupied_columns(sample)
    n, step, span = sample["grid"] - 1, sample["step"], sample["span"]
    width = max(1, min(n, round(n * cut)))
    mask = (1 << max(0, min(384, int(y_limit) + 64))) - 1
    mask &= ~((1 << max(0, min(384, int(floor_y) + 64))) - 1)
    columns = [[bits & mask for bits in row] for row in columns]
    mesh = []

    def face(points, normal, y, top=False):
        mesh.append((points, normal, y, top))

    for z in range(n):
        for x in range(width):
            bits = columns[z][x]
            if not bits:
                continue
            px, pz = x * step - span / 2, z * step - span / 2
            for start, end in bit_runs(bits):
                low, high = start - 64, end - 64
                face(
                    [
                        (px, high, pz),
                        (px + step, high, pz),
                        (px + step, high, pz + step),
                        (px, high, pz + step),
                    ],
                    (0, 1, 0),
                    high,
                    high == sample["heights"][z][x],
                )
                face(
                    [
                        (px, low, pz),
                        (px + step, low, pz),
                        (px + step, low, pz + step),
                        (px, low, pz + step),
                    ],
                    (0, -1, 0),
                    low,
                )
            for dx, dz in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, nz = x + dx, z + dz
                other = columns[nz][nx] if 0 <= nx < width and 0 <= nz < n else 0
                for start, end in bit_runs(bits & ~other):
                    low, high = start - 64, end - 64
                    if dx:
                        fx = px + (step if dx > 0 else 0)
                        points = [
                            (fx, low, pz),
                            (fx, high, pz),
                            (fx, high, pz + step),
                            (fx, low, pz + step),
                        ]
                    else:
                        fz = pz + (step if dz > 0 else 0)
                        points = [
                            (px, low, fz),
                            (px, high, fz),
                            (px + step, high, fz),
                            (px + step, low, fz),
                        ]
                    face(points, (dx, 0, dz), (low + high) / 2)
    return mesh


class TerrainRenderer:
    def __init__(self):
        self.yaw = -0.72
        self.pitch = 0.62
        self.zoom = 1.0
        self.pan_x = self.pan_y = 0
        self.vertical = 1.0
        self.y_limit = 320
        self.cut = 1.0
        self.floor_y = -64
        self._mesh_key = None
        self._mesh = []

    def reset(self):
        self.__init__()

    def render(self, sample, size, palette, water=True, trees=True, wire=False):
        width, height = max(100, size[0]), max(100, size[1])
        image = Image.new("RGB", (width, height), "#111b26")
        draw = ImageDraw.Draw(image)
        n, span, step = sample["grid"] - 1, sample["span"], sample["step"]
        cy, sy, cp, sp = (
            math.cos(self.yaw),
            math.sin(self.yaw),
            math.cos(self.pitch),
            math.sin(self.pitch),
        )
        top = min(self.y_limit, sample["max_height"])
        mid = (self.floor_y + top) / 2
        scale = (
            min(
                width * 0.63 / span,
                height * 0.78 / max(1, (top - self.floor_y) * abs(cp) + span * abs(sp)),
            )
            * self.zoom
        )

        def project(point):
            x, y, z = point
            horizontal = cy * x - sy * z
            away = sy * x + cy * z
            elevation = (y - mid) * self.vertical
            return (
                width / 2 + self.pan_x + horizontal * scale,
                height * 0.48 + self.pan_y + (away * sp - elevation * cp) * scale,
                -away * cp - elevation * sp,
            )

        key = (id(sample), self.y_limit, self.cut, self.floor_y)
        if key != self._mesh_key:
            self._mesh = voxel_mesh(sample, self.y_limit, self.cut, self.floor_y)
            self._mesh_key = key
        faces = []

        def face(points, color, courses=False):
            projected = [project(p) for p in points]
            lines = []
            if courses and wire and scale > 2.5:
                low, high = points[0][1], points[1][1]
                for y in range(math.floor(low) + 1, math.ceil(high)):
                    t = (y - low) / (high - low)
                    a = project(
                        tuple(
                            points[0][i] + t * (points[1][i] - points[0][i])
                            for i in range(3)
                        )
                    )
                    b = project(
                        tuple(
                            points[3][i] + t * (points[2][i] - points[3][i])
                            for i in range(3)
                        )
                    )
                    lines.append((a[0], a[1], b[0], b[1]))
            faces.append(
                (
                    sum(p[2] for p in projected) / len(projected),
                    [(p[0], p[1]) for p in projected],
                    color,
                    lines,
                )
            )

        grass = palette.get("grass", (106, 134, 91))
        stone = palette.get("stone", (103, 109, 116))
        dirt = palette.get("dirt", (112, 88, 68))
        deep = palette.get("deepstone", (60, 65, 73))
        deep_y = palette.get("deep_y", 0)
        light = (-0.45, 0.83, -0.3)
        for points, normal, y, top in self._mesh:
            if normal[0] * sy * cp + normal[1] * sp + normal[2] * cy * cp <= 0:
                continue
            color = grass if top else deep if y < deep_y else stone
            if not top and points[0][1] > sample["max_height"] - 3:
                color = dirt
            brightness = 0.66 + 0.42 * max(0, sum(a * b for a, b in zip(normal, light)))
            face(points, shade(color, brightness), normal[1] == 0)
        sea = sample["sea_level"]
        floating = sample.get("worldgen", {}).get("terrain") == "Floating Islands"
        fluid = sample.get("worldgen", {}).get("fluid", "Water")
        if water and not floating and fluid != "Air" and sea < self.y_limit:
            for z in range(n):
                for x in range(min(n, round(n * self.cut))):
                    if sample["heights"][z][x] <= sea:
                        px, pz = x * step - span / 2, z * step - span / 2
                        face(
                            [
                                (px, sea, pz),
                                (px + step, sea, pz),
                                (px + step, sea, pz + step),
                                (px, sea, pz + step),
                            ],
                            (
                                (218, 91, 25)
                                if fluid == "Lava"
                                else palette.get("water", (50, 100, 139))
                            ),
                        )
        if trees and self.y_limit >= sample["max_height"]:
            rng = random.Random(int(sample["seed"]))
            first, second = palette.get("tree1_count", 3), palette.get("tree2_count", 2)
            count = min(400, round((first + second) * span * span / 256 * 0.08))
            for _ in range(count):
                x, z = rng.randrange(n), rng.randrange(n)
                y = sample["heights"][z][x]
                if y <= sea or x >= round(n * self.cut):
                    continue
                kind = (
                    "tree1"
                    if rng.random() < first / max(1, first + second)
                    else "tree2"
                )
                tx, tz = x * step - span / 2, z * step - span / 2
                for low, high, r, color in [
                    (y, y + 5, 0.5, palette.get(kind + "_log", (77, 62, 48))),
                    (y + 4, y + 7, 2, palette.get(kind + "_leaves", (66, 105, 64))),
                ]:
                    face(
                        [
                            (tx - r, high, tz - r),
                            (tx + r, high, tz - r),
                            (tx + r, high, tz + r),
                            (tx - r, high, tz + r),
                        ],
                        color,
                    )
                    for dx, dz in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        if dx * sy + dz * cy <= 0:
                            continue
                        points = [
                            (tx + dx * r - dz * r, low, tz + dz * r + dx * r),
                            (tx + dx * r - dz * r, high, tz + dz * r + dx * r),
                            (tx + dx * r + dz * r, high, tz + dz * r - dx * r),
                            (tx + dx * r + dz * r, low, tz + dz * r - dx * r),
                        ]
                        face(points, shade(color, 0.8 if dx else 0.68))
        for _, polygon, color, lines in sorted(faces, key=lambda p: p[0], reverse=True):
            draw.polygon(
                polygon, fill=color, outline=shade(color, 0.86) if wire else None
            )
            for line in lines:
                draw.line(line, fill=shade(color, 0.86))
        draw.rounded_rectangle(
            (14, 14, 380, 82), radius=7, fill="#172738", outline="#365069"
        )
        draw.text((25, 24), "MINECRAFT 26.3 / BLOCK TERRAIN", fill="#bcd8e9")
        draw.text(
            (25, 44),
            f"{span} x {span} blocks | sample spacing {step} | sea Y {sea}",
            fill="#e3edf6",
        )
        draw.text(
            (25, 62),
            f"Seed {sample['seed']} | X {sample['center_x']} Z {sample['center_z']}",
            fill="#9db5c8",
        )
        return image
