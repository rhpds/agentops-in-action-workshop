#!/usr/bin/env python3
"""Render a .excalidraw scene to PNG, with no Excalidraw and no network.

The PNG keeps the scene embedded in a tEXt chunk, exactly as an Excalidraw
export does, so the image can be dragged back into Excalidraw and edited.
Losing that silently is easy -- these assets are documented as carrying it.

Scene JSON -> SVG -> headless Chrome screenshot. Only the element subset that
exdraw.py emits is supported (rectangle, ellipse, text, arrow); anything else
is skipped loudly rather than silently mis-drawn.

Usage: render.py scene.excalidraw out.png [scale]
"""
import html, json, os, struct, subprocess, sys, tempfile, zlib

SCALE = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
PAD = 60
FONT = ("ui-sans-serif, -apple-system, 'Segoe UI', Roboto, "
        "'Helvetica Neue', Arial, sans-serif")


def esc(t):
    return html.escape(t, quote=True)


def arrowhead(x1, y1, x2, y2, colour, size=9):
    import math
    a = math.atan2(y2 - y1, x2 - x1)
    pts = [(x2, y2),
           (x2 - size * math.cos(a - math.pi / 7), y2 - size * math.sin(a - math.pi / 7)),
           (x2 - size * math.cos(a + math.pi / 7), y2 - size * math.sin(a + math.pi / 7))]
    d = " ".join("%.1f,%.1f" % p for p in pts)
    return '<polygon points="%s" fill="%s"/>' % (d, colour)



def embed_scene(png_path, scene):
    """Append the scene as Excalidraw's tEXt chunk, before IEND.

    Envelope format, copied from a genuine Excalidraw export:
      {"version":"1","encoding":"bstring","compressed":true,"encoded":<zlib>}
    `encoded` holds the deflated bytes as a latin-1 "binary string", so the
    whole chunk is latin-1 as the PNG spec requires for tEXt.
    """
    payload = zlib.compress(json.dumps(scene).encode("utf-8"))
    envelope = json.dumps({"version": "1", "encoding": "bstring",
                           "compressed": True,
                           "encoded": payload.decode("latin-1")},
                          ensure_ascii=False).encode("latin-1")
    chunk_body = b"application/vnd.excalidraw+json\x00" + envelope
    chunk = (struct.pack(">I", len(chunk_body)) + b"tEXt" + chunk_body
             + struct.pack(">I", zlib.crc32(b"tEXt" + chunk_body) & 0xffffffff))
    data = open(png_path, "rb").read()
    i = data.rindex(b"IEND") - 4
    open(png_path, "wb").write(data[:i] + chunk + data[i:])


def verify_embed(png_path, scene):
    """Read it straight back -- a corrupt chunk is invisible otherwise."""
    data = open(png_path, "rb").read()
    i = 8
    while i < len(data):
        ln = struct.unpack(">I", data[i:i + 4])[0]
        typ = data[i + 4:i + 8]
        if typ == b"tEXt":
            k, v = data[i + 8:i + 8 + ln].split(b"\x00", 1)
            if k == b"application/vnd.excalidraw+json":
                env = json.loads(v.decode("latin-1"))
                back = json.loads(zlib.decompress(
                    env["encoded"].encode("latin-1")).decode("utf-8"))
                assert len(back["elements"]) == len(scene["elements"]), "element count differs"
                return len(back["elements"])
        if typ == b"IEND":
            break
        i += 12 + ln
    raise AssertionError("no excalidraw chunk found after embedding")


def main():
    scene = json.load(open(sys.argv[1]))
    els = [e for e in scene["elements"] if not e.get("isDeleted")]

    xs, ys = [], []
    for e in els:
        if e["type"] == "arrow":
            for px, py in e["points"]:
                xs.append(e["x"] + px); ys.append(e["y"] + py)
        else:
            xs += [e["x"], e["x"] + e.get("width", 0)]
            ys += [e["y"], e["y"] + e.get("height", 0)]
    minx, miny, maxx, maxy = min(xs) - PAD, min(ys) - PAD, max(xs) + PAD, max(ys) + PAD
    w, h = maxx - minx, maxy - miny

    out = []
    skipped = 0
    for e in els:
        t = e["type"]
        stroke = e.get("strokeColor", "#1e1e1e")
        fill = e.get("backgroundColor", "transparent")
        dash = ' stroke-dasharray="9 7"' if e.get("strokeStyle") == "dashed" else ""
        sw = e.get("strokeWidth", 2)
        if t == "rectangle":
            r = 14 if e.get("roundness") else 0
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%d" '
                       'fill="%s" stroke="%s" stroke-width="%s"%s/>'
                       % (e["x"], e["y"], e["width"], e["height"], r, fill, stroke, sw, dash))
        elif t == "ellipse":
            out.append('<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f" fill="%s" '
                       'stroke="%s" stroke-width="%s"%s/>'
                       % (e["x"] + e["width"] / 2, e["y"] + e["height"] / 2,
                          e["width"] / 2, e["height"] / 2, fill, stroke, sw, dash))
        elif t == "text":
            fs = e.get("fontSize", 16)
            lh = fs * e.get("lineHeight", 1.25)
            anchor = {"left": "start", "center": "middle", "right": "end"}.get(
                e.get("textAlign", "left"), "start")
            x = e["x"] + (e.get("width", 0) / 2 if anchor == "middle" else 0)
            for i, line in enumerate(e["text"].split("\n")):
                if not line.strip():
                    continue
                out.append('<text x="%.1f" y="%.1f" font-family="%s" font-size="%s" '
                           'fill="%s" text-anchor="%s" xml:space="preserve">%s</text>'
                           % (x, e["y"] + lh * (i + 0.82), FONT, fs, stroke, anchor, esc(line)))
        elif t == "arrow":
            pts = [(e["x"] + px, e["y"] + py) for px, py in e["points"]]
            d = " ".join(("M %.1f %.1f" if i == 0 else "L %.1f %.1f") % p
                         for i, p in enumerate(pts))
            out.append('<path d="%s" fill="none" stroke="%s" stroke-width="%s" '
                       'stroke-linecap="round" stroke-linejoin="round"%s/>'
                       % (d, stroke, sw, dash))
            if e.get("endArrowhead"):
                out.append(arrowhead(*pts[-2], *pts[-1], stroke))
            if e.get("startArrowhead"):
                out.append(arrowhead(*pts[1], *pts[0], stroke))
        else:
            skipped += 1
    if skipped:
        print("WARNING: skipped %d unsupported element(s)" % skipped, file=sys.stderr)

    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%.0f" height="%.0f" '
           'viewBox="%.1f %.1f %.1f %.1f"><rect x="%.1f" y="%.1f" width="%.1f" '
           'height="%.1f" fill="#ffffff"/>%s</svg>'
           % (w * SCALE, h * SCALE, minx, miny, w, h, minx, miny, w, h, "".join(out)))

    d = tempfile.mkdtemp()
    page = os.path.join(d, "p.html")
    open(page, "w").write(
        "<html><head><meta charset='utf-8'><style>html,body{margin:0;padding:0}"
        "</style></head><body>%s</body></html>" % svg)
    subprocess.run(["google-chrome", "--headless", "--disable-gpu", "--no-sandbox",
                    "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--window-size=%d,%d" % (int(w * SCALE), int(h * SCALE)),
                    "--screenshot=" + os.path.abspath(sys.argv[2]),
                    "file://" + page],
                   check=True, capture_output=True, timeout=180)
    embed_scene(sys.argv[2], scene)
    n = verify_embed(sys.argv[2], scene)
    print("rendered %s  %dx%d  from %d elements  (scene embedded + verified: %d)"
          % (sys.argv[2], int(w * SCALE), int(h * SCALE), len(els), n))


main()
