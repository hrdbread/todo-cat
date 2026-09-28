#!/usr/bin/env python3
"""Generate 16 walking frames from a sprite sheet.
Usage: python3 tools/mkframes.py <sprite-sheet.png> [cat]   (8 frames in one row, walking right; writes to assets/pets/<cat>/, default sprout)"""
from AppKit import (NSImage, NSBitmapImageRep, NSGraphicsContext, NSColor,
                    NSCompositingOperationSourceOver, NSRectFill,
                    NSBitmapImageFileTypePNG, NSAffineTransform,
                    NSCalibratedRGBColorSpace)
from Foundation import NSMakeRect
from pathlib import Path
from collections import deque

import sys
HOME = (Path(__file__).resolve().parents[1] / "assets" / "pets"
        / (sys.argv[2] if len(sys.argv) > 2 else "sprout"))   # output dir
HOME.mkdir(parents=True, exist_ok=True)
if len(sys.argv) < 2:
    sys.exit(__doc__)
SRC = Path(sys.argv[1]).expanduser()
BAND = (108, 284)          # 'Walk Right' row
COLS = [(44,214),(241,401),(430,593),(617,778),(804,969),(990,1165),(1175,1335),(1352,1496)]
TH = 104                   # final frame height

src = NSImage.alloc().initWithContentsOfFile_(str(SRC))
SW, SH = int(src.size().width), int(src.size().height)

def render_region(x0, y0, x1, y1, scale=1):
    """Render a y-down region of the source into a bitmap (white background)."""
    w, h = int((x1 - x0) * scale), int((y1 - y0) * scale)
    rep = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, w, h, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 0)
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.setCurrentContext_(ctx)
    NSColor.whiteColor().setFill(); NSRectFill(NSMakeRect(0, 0, w, h))
    src.drawInRect_fromRect_operation_fraction_(
        NSMakeRect(0, 0, w, h),
        NSMakeRect(x0, SH - y1, x1 - x0, y1 - y0),   # flip y
        NSCompositingOperationSourceOver, 1.0)
    NSGraphicsContext.restoreGraphicsState()
    return rep, w, h

def to_rgba_with_transparency(rep, w, h):
    """Flood-fill from the edges to make only the white background transparent."""
    def isw(x, y):
        c = rep.colorAtX_y_(x, y).colorUsingColorSpaceName_(NSCalibratedRGBColorSpace)
        return (c.redComponent() > 0.91 and c.greenComponent() > 0.91
                and c.blueComponent() > 0.91)
    clear = [[False]*w for _ in range(h)]
    q = deque()
    for x in range(w):
        for y in (0, h-1):
            if isw(x, y) and not clear[y][x]:
                clear[y][x] = True; q.append((x, y))
    for y in range(h):
        for x in (0, w-1):
            if isw(x, y) and not clear[y][x]:
                clear[y][x] = True; q.append((x, y))
    while q:
        x, y = q.popleft()
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = x+dx, y+dy
            if 0 <= nx < w and 0 <= ny < h and not clear[ny][nx] and isw(nx, ny):
                clear[ny][nx] = True; q.append((nx, ny))
    out = NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, w, h, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 0)
    for y in range(h):
        for x in range(w):
            if clear[y][x]:
                out.setColor_atX_y_(NSColor.clearColor(), x, y)
            else:
                out.setColor_atX_y_(rep.colorAtX_y_(x, y), x, y)
    return out


def bbox(rep, w, h):
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        for x in range(w):
            if rep.colorAtX_y_(x, y).colorUsingColorSpaceName_(
                    NSCalibratedRGBColorSpace).alphaComponent() > 0.35:
                if x < minx: minx = x
                if x > maxx: maxx = x
                if y < miny: miny = y
                if y > maxy: maxy = y
    return minx, miny, maxx, maxy


def save_png(img, name):
    rep = NSBitmapImageRep.imageRepWithData_(img.TIFFRepresentation())
    rep.representationUsingType_properties_(
        NSBitmapImageFileTypePNG, None).writeToFile_atomically_(
        str(HOME / name), True)


# 1) render each frame at 2x → transparency → bbox
cut = []
for (x0, x1) in COLS:
    rep, w, h = render_region(x0 - 6, BAND[0], x1 + 6, BAND[1], scale=2)
    rep = to_rgba_with_transparency(rep, w, h)
    bx = bbox(rep, w, h)
    cut.append((rep, w, h, bx))
    print("frame", len(cut), "bbox", bx)

# 2) common canvas (feet aligned to bottom, centered horizontally)
bw = max(b[2] - b[0] + 1 for _, _, _, b in cut)
bh = max(b[3] - b[1] + 1 for _, _, _, b in cut)
scale = TH / (bh / 2.0)          # rendered at 2x
CW = int(bw / 2.0 * scale) + 8
CH = TH + 4
print("canvas:", CW, CH)

for i, (rep, w, h, b) in enumerate(cut, 1):
    src_img = NSImage.alloc().initWithSize_((w, h))
    src_img.addRepresentation_(rep)
    fw, fh = (b[2] - b[0] + 1), (b[3] - b[1] + 1)
    dw, dh = fw / 2.0 * scale, fh / 2.0 * scale
    canvas = NSImage.alloc().initWithSize_((CW, CH))
    canvas.lockFocus()
    src_img.drawInRect_fromRect_operation_fraction_(
        NSMakeRect((CW - dw) / 2, 2, dw, dh),          # bottom-aligned
        NSMakeRect(b[0], h - b[3] - 1, fw, fh),        # flip y
        NSCompositingOperationSourceOver, 1.0)
    canvas.unlockFocus()
    save_png(canvas, f"walk{i}.png")
    # mirrored copy
    flip = NSImage.alloc().initWithSize_((CW, CH))
    flip.lockFocus()
    t = NSAffineTransform.transform()
    t.translateXBy_yBy_(CW, 0); t.scaleXBy_yBy_(-1, 1); t.concat()
    canvas.drawInRect_fromRect_operation_fraction_(
        NSMakeRect(0, 0, CW, CH), NSMakeRect(0, 0, CW, CH),
        NSCompositingOperationSourceOver, 1.0)
    flip.unlockFocus()
    save_png(flip, f"walk{i}_flip.png")
print("16 FRAMES SAVED", CW, CH)
