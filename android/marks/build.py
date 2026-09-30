"""The apps' marks.

    docker build -t opus-mark .
    docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/../..:/repo" -w /repo/android/marks opus-mark python build.py

The TV app is OPUS Player and wears the family's O: its launcher icon and leanback
banner are the vectors opus-ui derives (frontend/src/lib/opus/marks/android/),
copied in because the Android build sees only this directory. OPUS Music keeps
its own initial, drawn from the repository's Inter; its colours are named, not
written, so that mark and the app share core/src/main/res/values/colors.xml.
"""

import io
import subprocess
from pathlib import Path

from PIL import Image

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = Path(__file__).resolve().parent
ANDROID = HERE.parent
FONT = ANDROID.parent / "frontend" / "static" / "fonts" / "inter-latin.woff2"
FAMILY = ANDROID.parent / "frontend" / "src" / "lib" / "opus" / "marks" / "android"
TILE = ANDROID / "app" / "src" / "main" / "assets" / "apps" / "biz.boskovic.opus.player.png"
NS = 'xmlns:android="http://schemas.android.com/apk/res/android"'


def number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


class Face:
    def __init__(self, weight: int):
        self.font = instantiateVariableFont(TTFont(FONT), {"wght": weight})
        self.glyphs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()
        self.em = self.font["head"].unitsPerEm

    def name(self, letter: str) -> str:
        return self.cmap[ord(letter)]

    def advance(self, letter: str, size: float) -> float:
        return self.font["hmtx"][self.name(letter)][0] * size / self.em

    def bounds(self, letter: str, size: float) -> tuple[float, float, float, float]:
        pen = BoundsPen(self.glyphs)
        self.glyphs[self.name(letter)].draw(pen)
        left, bottom, right, top = pen.bounds
        scale = size / self.em
        return left * scale, bottom * scale, right * scale, top * scale

    def path(self, letter: str, size: float, x: float, baseline: float) -> str:
        pen = SVGPathPen(self.glyphs, ntos=number)
        scale = size / self.em
        self.glyphs[self.name(letter)].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
        return pen.getCommands()


def vector(width: int, height: int, paths: list[tuple[str, str]]) -> str:
    body = "\n".join(
        f'    <path\n        android:fillColor="@color/{colour}"\n        android:pathData="{data}" />'
        for colour, data in paths
    )
    return (
        f'<?xml version="1.0" encoding="utf-8"?>\n<vector {NS}\n'
        f'    android:width="{width}dp"\n    android:height="{height}dp"\n'
        f'    android:viewportWidth="{width}"\n    android:viewportHeight="{height}">\n{body}\n</vector>\n'
    )


def mark(face: Face, initial: str) -> str:
    """The initial alone, sized for the 72 dp an adaptive icon shows of its
    108 dp canvas: a word does not survive a launcher tile."""
    canvas, size = 108, 72 * 0.62
    left, bottom, right, top = face.bounds(initial, size)
    x = canvas / 2 - (left + right) / 2
    baseline = canvas / 2 + (bottom + top) / 2
    return vector(canvas, canvas, [("opus_accent", face.path(initial, size, x, baseline))])


ICON = f"""<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon {NS}>
    <background android:drawable="@color/opus_ground" />
    <foreground android:drawable="@drawable/mark" />
    <monochrome android:drawable="@drawable/mark" />
</adaptive-icon>
"""


def put(module: str, where: str, text: str):
    path = ANDROID / module / "src" / "main" / "res" / where
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    print(f"  {module}/{where}")


PLAYER_ICON = f"""<?xml version="1.0" encoding="utf-8"?>
<adaptive-icon {NS}>
    <background android:drawable="@drawable/opus_tile" />
    <foreground android:drawable="@drawable/opus_mark" />
    <monochrome android:drawable="@drawable/opus_mark" />
</adaptive-icon>
"""


def tile():
    """The Home launcher's tile: the lockup fitted into the box every app's art
    keeps on its 640x360 canvas, so OPUS stands the size the others stand."""
    box_w, box_h = 384, 104
    drawn = subprocess.run(
        ["rsvg-convert", "-w", str(box_w * 4), str(FAMILY.parent / "opus-player.svg")],
        capture_output=True, check=True).stdout
    logo = Image.open(io.BytesIO(drawn)).convert("RGBA")
    scale = min(box_w / logo.width, box_h / logo.height)
    logo = logo.resize((round(logo.width * scale), round(logo.height * scale)), Image.LANCZOS)
    canvas = Image.new("RGBA", (640, 360), (0, 0, 0, 0))
    canvas.alpha_composite(logo, ((640 - logo.width) // 2, (360 - logo.height) // 2))
    canvas.save(TILE, optimize=True)
    print(f"  {TILE.relative_to(ANDROID)}")


if __name__ == "__main__":
    for name in ("opus_mark.xml", "opus_tile.xml", "player_banner.xml"):
        put("app", f"drawable/{name}", (FAMILY / name).read_text())
    put("app", "mipmap-anydpi/ic_launcher.xml", PLAYER_ICON)
    tile()
    face = Face(800)
    put("music", "drawable/mark.xml", mark(face, "M"))
    put("music", "mipmap-anydpi/ic_launcher.xml", ICON)
