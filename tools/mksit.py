#!/usr/bin/env python3
"""Sitting-cat artwork → cat.png / pet_alert.png / pet_happy.png (+flip)
   Usage: python3 tools/mksit.py <sitting-cat.png> [cat]   (writes to assets/pets/<cat>/, default sprout)
   Writes pixels directly into NSBitmapImageRep (no lockFocus, guaranteed RGBA)."""
from AppKit import (NSImage, NSBitmapImageRep, NSGraphicsContext, NSColor,
                    NSCompositingOperationSourceOver, NSRectFill, NSBezierPath,
                    NSBitmapImageFileTypePNG, NSCalibratedRGBColorSpace,
                    NSAffineTransform)
from Foundation import NSMakeRect
from pathlib import Path
from collections import deque
import math

import sys
HOME = (Path(__file__).resolve().parents[1] / "assets" / "pets"
        / (sys.argv[2] if len(sys.argv) > 2 else "sprout"))   # output dir
HOME.mkdir(parents=True, exist_ok=True)
if len(sys.argv) < 2:
    sys.exit(__doc__)
SRC = Path(sys.argv[1]).expanduser()
TH = 400                                   # final height

src = NSImage.alloc().initWithContentsOfFile_(str(SRC))
SW, SH = int(src.size().width), int(src.size().height)

def new_rep(w, h):
    return NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, w, h, 8, 4, True, False, NSCalibratedRGBColorSpace, 0, 0)

def draw_into(rep, fn):
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState(); NSGraphicsContext.setCurrentContext_(ctx)
    fn(); NSGraphicsContext.restoreGraphicsState()

def save(rep, name):
    rep.representationUsingType_properties_(
        NSBitmapImageFileTypePNG, None).writeToFile_atomically_(str(HOME / name), True)

# 1) render source at 0.5x (512) on white → flood-fill transparency → bbox
w, h = SW // 2, SH // 2
base = new_rep(w, h)
def d0():
    NSColor.whiteColor().setFill(); NSRectFill(NSMakeRect(0, 0, w, h))
    src.drawInRect_fromRect_operation_fraction_(
        NSMakeRect(0, 0, w, h), NSMakeRect(0, 0, SW, SH),
        NSCompositingOperationSourceOver, 1.0)
draw_into(base, d0)
def isw(x, y):
    c = base.colorAtX_y_(x, y).colorUsingColorSpaceName_(NSCalibratedRGBColorSpace)
    return c.redComponent() > 0.9 and c.greenComponent() > 0.9 and c.blueComponent() > 0.9
clear = [[False]*w for _ in range(h)]
q = deque()
for x in range(w):
    for y in (0, h-1):
        if isw(x, y) and not clear[y][x]: clear[y][x] = True; q.append((x, y))
for y in range(h):
    for x in (0, w-1):
        if isw(x, y) and not clear[y][x]: clear[y][x] = True; q.append((x, y))
while q:
    x, y = q.popleft()
    for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx, ny = x+dx, y+dy
        if 0 <= nx < w and 0 <= ny < h and not clear[ny][nx] and isw(nx, ny):
            clear[ny][nx] = True; q.append((nx, ny))
trans = new_rep(w, h)
minx, miny, maxx, maxy = w, h, 0, 0
for y in range(h):
    for x in range(w):
        if clear[y][x]:
            trans.setColor_atX_y_(NSColor.clearColor(), x, y)
        else:
            trans.setColor_atX_y_(base.colorAtX_y_(x, y), x, y)
            minx, miny, maxx, maxy = min(minx,x), min(miny,y), max(maxx,x), max(maxy,y)
fw, fh = maxx-minx+1, maxy-miny+1
print("bbox (512px space):", minx, miny, maxx, maxy)

# 2) crop + scale to height 400 → cat.png
sc = TH / fh
TW = int(round(fw * sc))
timg = NSImage.alloc().initWithSize_((w, h)); timg.addRepresentation_(trans)
def make_base():
    rep = new_rep(TW, TH)
    def d():
        NSColor.clearColor().setFill(); NSRectFill(NSMakeRect(0, 0, TW, TH))
        timg.drawInRect_fromRect_operation_fraction_(
            NSMakeRect(0, 0, TW, TH), NSMakeRect(minx, h - maxy - 1, fw, fh),
            NSCompositingOperationSourceOver, 1.0)
    draw_into(rep, d)
    return rep
save(make_base(), "cat.png")

# source (1024px) coords → output coords (AppKit y-up)
def P(X, Y):
    return ((X / 2 - minx) * sc, TH - (Y / 2 - miny) * sc)
K = sc / 2                       # 1024px length → output length
INK = NSColor.colorWithSRGBRed_green_blue_alpha_(0.16, 0.16, 0.15, 1)
EYES = ((451, 376), (517, 376))  # eye centers in 1024px space (measured)

# 3) alert: wide-open eyes
al = make_base()
def d_alert():
    for (X, Y) in EYES:
        x, y = P(X, Y)
        rw, rh = 20 * K, 13 * K
        NSColor.whiteColor().setFill()
        NSBezierPath.bezierPathWithOvalInRect_(((x - rw, y - rh), (rw*2, rh*2))).fill()
        INK.setStroke()
        pp = NSBezierPath.bezierPathWithOvalInRect_(((x - rw, y - rh), (rw*2, rh*2)))
        pp.setLineWidth_(2 * K); pp.stroke()
        r = 10.8 * K
        INK.setFill()
        NSBezierPath.bezierPathWithOvalInRect_(((x - r, y - r), (r*2, r*2))).fill()
        NSColor.whiteColor().setFill()
        NSBezierPath.bezierPathWithOvalInRect_(((x - r + 1.6*K, y + r*0.1), (r*0.62, r*0.62))).fill()
draw_into(al, d_alert)
save(al, "pet_alert.png")

# 4) happy: blush
hp = make_base()
def d_happy():
    NSColor.colorWithSRGBRed_green_blue_alpha_(0.93, 0.59, 0.56, 0.5).setFill()
    for (X0, Y0, X1, Y1) in ((430, 390, 461, 405), (505, 390, 536, 405)):
        x0, y1 = P(X0, Y1); x1, y0 = P(X1, Y0)
        NSBezierPath.bezierPathWithOvalInRect_(((x0, y1), (x1 - x0, y0 - y1))).fill()
draw_into(hp, d_happy)
save(hp, "pet_happy.png")

# 5) mirrored copies
for name in ("cat", "pet_alert", "pet_happy"):
    im = NSImage.alloc().initWithContentsOfFile_(str(HOME / f"{name}.png"))
    rep = new_rep(TW, TH)
    def d():
        NSColor.clearColor().setFill(); NSRectFill(NSMakeRect(0, 0, TW, TH))
        t = NSAffineTransform.transform(); t.translateXBy_yBy_(TW, 0); t.scaleXBy_yBy_(-1, 1); t.concat()
        im.drawInRect_fromRect_operation_fraction_(
            NSMakeRect(0, 0, TW, TH), NSMakeRect(0, 0, TW, TH),
            NSCompositingOperationSourceOver, 1.0)
    draw_into(rep, d)
    save(rep, f"{name}_flip.png")
print(f"DONE: {TW}x{TH}, eyes at {P(*EYES[0])}, {P(*EYES[1])}")
