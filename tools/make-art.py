#!/usr/bin/env python3
"""
make-art.py — turn a photograph into an embedded ascii piece for this blog.

Pipeline, per note:

    wallhaven search -> download -> aspect crop -> downsample to the character
    grid -> luminance ramp (the glyphs) + median-cut palette (the colours)
    -> src/art/<slug>.js, a module in the ascii.rest piece shape.

The module is a coloured piece: `meta.palette` holds up to 64 colours and the
frame function writes one palette index per cell into `env.color`, so ascii.rest
draws it on a canvas. It also renders as plain one-ink text when no colour
buffer is offered, so the same module works in a `<pre>`.

Animation is generated, not stored: the final image is the data, and a
deterministic hash decides which cells have "decoded" yet, so the piece plays a
short decode reveal and then holds. Frames are never shipped.

Usage:
    python tools/make-art.py --all              # every note in the table below
    python tools/make-art.py --only docker-has-two-stores
    python tools/make-art.py --only x --print   # print the ascii, write nothing

Queries are fragile: wallhaven's search is an AND over a narrow tag vocabulary,
so multi-word queries often return nothing ("railway switchyard", "pressure
gauge") and a few ordinary words are simply untagged ("printing", "abacus").
Each query is therefore tried as written, then as its individual words
longest-first, each with and without the ratio/size filters — which recovered
10 of the 11 failures the first full run produced, measured.

Sources: wallhaven.cc (public API, SFW only). Each generated module records the
source image id and URL in a header comment, and the .art-src/ sidecar keeps the
full metadata. Check the licence of anything you actually publish: wallhaven
hosts user uploads with varying terms.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import pathlib
import re
import sys
import time
import urllib.parse
import urllib.request

from PIL import Image, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / ".art-src"
OUT_DIR = ROOT / "src" / "art" / "pieces"
INDEX_FILE = ROOT / "src" / "art" / "sources.js"

COLS = 132
ROWS = 37
# density ramp: index 0 is the darkest cell, the last is the brightest
RAMP = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "

# slug -> (search query, fallbacks)
TOPICS: dict[str, tuple[str, list[str]]] = {
    "anonymising-real-work": ("glitch art abstract", ["digital noise", "static interference"]),
    "a-successful-command-is-not-a-successful-task": ("gauge", ["instrument dial", "compass brass"]),
    "moving-dockers-storage-to-another-disk": ("container ship sea", ["cargo ship", "shipping container yard"]),
    "moving-a-stack-between-reverse-proxies": ("railway switchyard", ["train tracks aerial", "railway junction"]),
    "drives-that-are-not-there": ("hard disk platter macro", ["hard drive", "circuit board macro"]),
    "reaching-a-service-over-a-tailnet": ("night tunnel lights", ["tunnel road", "cave passage"]),
    "driving-wsl-from-the-windows-side": ("penguin snow", ["penguin", "arctic ice"]),
    "triage-on-a-host-you-cannot-see": ("retro computer terminal", ["vintage computer", "green screen monitor"]),
    "an-element-existing-is-not-a-page-rendering": ("glitch screen pixels", ["broken tv static", "digital distortion"]),
    "csv-that-survives-both-excel-and-an-importer": ("graph paper grid", ["blueprint grid", "ledger columns"]),
    "proving-row-level-security": ("padlock chain", ["padlock", "vault door"]),
    "declarative-config-the-machine-is-the-file": ("blueprint schematic", ["technical drawing", "engineer blueprint"]),
    "the-conflict-you-cannot-see": ("labyrinth maze", ["hedge maze", "stone maze"]),
    "offline-first-sync-and-the-queue-that-survives-a-crash": ("desert dunes road", ["sand dunes", "desert highway"]),
    # "letterpress" and "printing" are dead tags on wallhaven (total: 0), so this
    # one leads with a word that exists
    "static-sites-and-the-content-pipeline": ("typewriter keys", ["typewriter", "manuscript"]),
    "the-terminal-as-a-design-language": ("neon matrix rain", ["cyberpunk neon rain", "digital rain"]),
    "delegating-work-to-parallel-agents": ("starling murmuration", ["flock of birds", "birds swarm"]),
    "measure-the-part-not-the-datasheet": ("caliper", ["micrometer", "measuring tools", "ruler metal"]),
    "a-backup-you-never-restored-is-a-hypothesis": ("hourglass sand", ["hourglass", "antique clock gears"]),
    "docker-has-two-stores": ("harbor", ["warehouse", "cranes port", "shipping containers"]),
    "a-mount-check-that-stayed-quiet": ("lighthouse fog", ["foggy forest", "lighthouse storm"]),
    "reinstalling-a-server-you-cannot-reach": ("satellite dish night sky", ["radio telescope", "space observatory"]),
    # second wave: lessons from other projects
    "three-clients-one-session": ("keyhole door", ["keys vintage", "locksmith"]),
    "multi-tenant-by-default": ("apartment building facade", ["city apartments", "windows building"]),
    "a-portal-you-do-not-control": ("modern office glass", ["architecture abstract", "atrium skylight"]),
    "authenticated-scraping": ("spider web dew", ["spider web", "cobweb morning"]),
    "a-test-suite-you-can-regenerate": ("manuscript", ["newspaper", "books", "typewriter"]),
    "spreadsheets-built-by-code": ("calculator", ["grid", "chalkboard", "columns"]),
    "a-unique-index-that-does-not-deduplicate": ("dominoes falling", ["domino tiles", "marbles pattern"]),
    "testing-on-an-emulator": ("arcade machine", ["retro arcade", "game console vintage"]),
    "the-one-page-report-that-spilled": ("stack of paper", ["paper sheets stack", "typewriter paper"]),
    "payments-that-authorise-before-they-charge": ("banknotes coins", ["credit card macro", "vintage cash register"]),
}


def api_search(query: str, page: int = 1, strict: bool = True) -> list[dict]:
    params = {
        "q": query,
        "categories": "100",   # general only
        "purity": "100",       # SFW only
        "sorting": "relevance",
        "page": str(page),
    }
    if strict:
        # exact wallpaper shape first; a narrow query often has nothing here
        params["ratios"] = "16x9"
        params["atleast"] = "1920x1080"
    url = "https://wallhaven.cc/api/v1/search?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "terminal-notes-art/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    time.sleep(1.2)  # be a good citizen on a public API
    return [
        w
        for w in payload.get("data", [])
        if w.get("file_type") == "image/jpeg"
        # the strict pass already filtered by size server-side; this catches the
        # loose pass, where thumbnails are not worth decoding
        and int(w.get("dimension_x", 0)) >= 1280
    ]


def fetch(url: str, dest: pathlib.Path) -> bytes:
    if dest.exists():
        return dest.read_bytes()
    req = urllib.request.Request(url, headers={"User-Agent": "terminal-notes-art/1.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        data = r.read()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return data


def to_grid(img: Image.Image, cols: int, rows: int) -> Image.Image:
    """Centre-crop to the character grid's aspect, then downsample."""
    target = cols / (rows * 2)          # a character cell is twice as tall as wide
    w, h = img.size
    if w / h > target:
        w = int(h * target)
        img = img.crop(((img.width - w) // 2, 0, (img.width - w) // 2 + w, h))
    else:
        h = int(w / target)
        img = img.crop((0, (img.height - h) // 2, w, (img.height - h) // 2 + h))
    return img.resize((cols, rows), Image.LANCZOS)


def candidate_queries(query: str) -> list[str]:
    """The query itself, then its words longest-first.

    wallhaven's search is an AND over tags with a narrow vocabulary, so a
    two- or three-word query is the fragile shape: "railway switchyard" and
    "pressure gauge" return nothing at all, while their individual words are
    well populated. Trying the longest word first keeps the result as specific
    as the vocabulary allows without hand-tuning every entry in TOPICS.
    """
    words = [w for w in re.split(r"\s+", query.strip()) if len(w) > 3]
    words.sort(key=len, reverse=True)
    out = [query]
    for w in words:
        if w.lower() not in {o.lower() for o in out}:
            out.append(w)
    return out


def find_image(query: str) -> tuple[dict, str]:
    """First hit for the first candidate query that has any, with the query used."""
    for candidate in candidate_queries(query):
        for strict in (True, False):
            hits = api_search(candidate, strict=strict)
            if hits:
                return hits[0], candidate
    raise SystemExit(f"no wallhaven results for {query!r} (or any single word of it)")


def build(slug: str, query: str, cols: int, rows: int, print_only: bool = False) -> dict:
    pick, used_query = find_image(query)
    query = used_query
    raw = fetch(pick["path"], SRC_DIR / f"{pick['id']}{pathlib.Path(pick['path']).suffix}")
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    grid = to_grid(img, cols, rows)

    # --- glyphs: luminance, mapped through the density ramp ------------------
    # autocontrast first: a photograph that is all midtones (a night shot, a
    # dim room) maps to one narrow band of the ramp and reads as noise. The
    # stretch opens the subject up.
    lum = ImageOps.autocontrast(to_grid(img, cols, rows).convert("L"), cutoff=1)
    ramp = RAMP
    # The picture sits on a dark ground, so LIGHT pixels are the dense glyphs:
    # walking the ramp from the bright end is what stops the image reading as a
    # photographic negative.
    cells = [round((1 - v / 255) * (len(ramp) - 1)) for v in lum.getdata()]
    glyphs = "".join(ramp[i] for i in cells)

    # --- colours: median cut to a palette ascii.rest can carry (max 64) -----
    paletted = grid.quantize(colors=64, method=Image.MEDIANCUT)
    pal = paletted.getpalette() or []
    # the palette is padded out to 64 entries; keep only what the image uses
    used = sorted(set(paletted.getdata()))
    remap = {old: new for new, old in enumerate(used)}
    if len(used) > 64:
        raise SystemExit("palette overflow")
    palette = [
        "#%02x%02x%02x" % (pal[i * 3], pal[i * 3 + 1], pal[i * 3 + 2]) for i in used
    ]
    indices = bytes(remap[p] for p in paletted.getdata())

    # ground: the darkest colour the image uses, for behind the cells
    darkest = min(used, key=lambda i: pal[i * 3] + pal[i * 3 + 1] + pal[i * 3 + 2])
    ground = "#%02x%02x%02x" % (pal[darkest * 3], pal[darkest * 3 + 1], pal[darkest * 3 + 2])

    meta = {
        "slug": slug,
        "query": query,
        "source_id": pick["id"],
        "source_url": pick["path"],
        "source_page": pick.get("url"),
        "resolution": pick.get("resolution"),
        "colors": len(palette),
    }

    if print_only:
        for r in range(rows):
            print(glyphs[r * cols : (r + 1) * cols])
        print(f"\n[{slug}] {meta['resolution']} -> {cols}x{rows}, {len(palette)} colours, ground {ground}")
        return meta

    module = render_module(slug, cols, rows, glyphs, palette, indices, ground, meta)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{slug}.js").write_text(module, encoding="utf-8", newline="\n")
    meta["bytes"] = len(module)
    (SRC_DIR / f"{slug}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"  {slug:<46} {meta['resolution']:>10} -> {cols}x{rows}  {len(palette):>2} colours  {len(module)/1024:>5.1f} KB")
    return meta


def b64(data: bytes) -> str:
    import base64

    return base64.b64encode(data).decode()


def js_literal(s: str) -> str:
    """A python string as a double-quoted JS string literal.

    Hoisted out of the f-string on purpose: an f-string expression may not
    contain a backslash before Python 3.12, which is exactly the kind of
    thing that costs twenty minutes.
    """
    out = []
    for ch in s:
        if ch in '\\"':
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\n")
        else:
            out.append(ch)
    return '"' + "".join(out) + '"'


def render_module(
    slug: str, cols: int, rows: int, glyphs: str, palette: list[str],
    indices: bytes, ground: str, meta: dict,
) -> str:
    """The piece module: data plus a decode reveal generated at run time."""
    palette_js = ",\n  ".join(
        ", ".join(f'"{c}"' for c in palette[i : i + 8]) for i in range(0, len(palette), 8)
    )
    glyph_literal = js_literal(glyphs)
    ramp_literal = js_literal(RAMP)
    return f'''/*
 * ascii art for "{slug}" — generated by tools/make-art.py, do not edit by hand.
 *
 * source: wallhaven image {meta['source_id']} ({meta['resolution']})
 *         {meta['source_url']}
 * query:  {meta['query']}
 *
 * A coloured piece in the ascii.rest shape: {rows} rows of {cols} cells, one
 * palette index per cell in `env.color`, drawn on a canvas. It plays a short
 * decode reveal on mount and then holds the picture.
 */
export const meta = {{
  name: "{slug}",
  category: "scenes",
  note: "a photograph of {meta['query']}, decoded to {cols} by {rows} characters",
  cols: {cols},
  rows: {rows},
  fps: 30,
  cell: 2,
  ground: "{ground}",
  palette: [
  {palette_js},
  ],
}};

/** The finished picture, one `cols`-wide line per row. Also the no-JS and
 *  reduced-motion still, so those readers get the image rather than the noise. */
export const still = {glyph_literal};

const GLYPHS = still;
const COLORS = Uint8Array.from(atob("{b64(indices)}"), (c) => c.charCodeAt(0));
const RAMP = {ramp_literal};
/* undecoded cells: a dim mid-tone, so the picture emerges rather than flashes */
const NOISE = {max(1, len(palette) // 3)};
const N = {cols * rows};
const COLS = {cols};

/** deterministic 0..1 per cell, so the reveal order never changes between loads */
function hash(i, salt) {{
  let h = (i * 2654435761) ^ (salt * 40503);
  h = (h ^ (h >>> 15)) * 2246822519;
  h = (h ^ (h >>> 13)) * 3266489917;
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}}

const FINAL = (() => {{
  const out = new Array(N);
  for (let i = 0; i < N; i++) out[i] = GLYPHS.charCodeAt(i);
  return out;
}})();

export default function piece() {{
  const scratch = new Uint8Array(N);
  return (t, env) => {{
    /* decode fast, then hold: a long scramble is noise, not art */
    const p = Math.min(1, Math.pow(t / 1.2, 0.6));
    if (p >= 1) {{
      if (env && env.color) env.color.set(COLORS);
      return GLYPHS;
    }}
    const frame = (t * meta.fps) | 0;
    const codes = new Array(N);
    for (let i = 0; i < N; i++) {{
      if (hash(i, 7) < p) {{
        codes[i] = FINAL[i];
        scratch[i] = COLORS[i];
      }} else {{
        /* still decoding: noise, never a letter of the picture */
        codes[i] = RAMP.charCodeAt((hash(i, frame + 11) * (RAMP.length - 1)) | 0);
        scratch[i] = NOISE;
      }}
    }}
    let s = "";
    for (let r = 0; r < {rows}; r++) {{
      for (let c = 0; c < COLS; c++) s += String.fromCharCode(codes[r * COLS + c]);
      if (r < {rows} - 1) s += "\\n";
    }}
    if (env && env.color) env.color.set(scratch);
    return s;
  }};
}}
'''


def write_source_index(sources: dict[str, dict]) -> None:
    """src/art/sources.js — where each picture came from, for the captions.

    Generated from the same metadata the modules carry, so a note's caption can
    credit the photograph it was decoded from without duplicating the URL into
    the markdown.
    """
    rows = []
    for slug in sorted(sources):
        s = sources[slug]
        rows.append(
            f"  {json.dumps(slug)}: {{ id: {json.dumps(s['source_id'])}, "
            f"page: {json.dumps(s.get('source_page') or s['source_url'])}, "
            f"query: {json.dumps(s['query'])}, resolution: {json.dumps(s.get('resolution', ''))} }},"
        )
    INDEX_FILE.write_text(
        "/*\n"
        " * Where the ascii art came from. Generated by tools/make-art.py from\n"
        " * wallhaven.cc search results — check the terms of any image before you\n"
        " * publish it; wallhaven hosts user uploads with varying licences.\n"
        " */\n"
        "export const sources = {\n" + "\n".join(rows) + "\n};\n\n"
        "export function getSource(slug) {\n"
        "  return sources[slug];\n"
        "}\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="a single note slug from the table")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--cols", type=int, default=COLS)
    ap.add_argument("--rows", type=int, default=ROWS)
    ap.add_argument("--print", dest="print_only", action="store_true")
    args = ap.parse_args()

    if args.only:
        if args.only not in TOPICS:
            raise SystemExit(f"unknown slug {args.only!r}; known: {', '.join(TOPICS)}")
        slugs = [args.only]
    elif args.all:
        slugs = list(TOPICS)
    else:
        raise SystemExit("pass --all or --only <slug>")

    if not slugs:
        return 1
    if len(slugs) > 1:
        print(f"generating {len(slugs)} pieces into {OUT_DIR.relative_to(ROOT)}/")
    metas = []
    failures = []
    for slug in slugs:
        query, fallbacks = TOPICS[slug]
        for candidate in [query, *fallbacks]:
            try:
                metas.append(build(slug, candidate, args.cols, args.rows, args.print_only))
                break
            except SystemExit as exc:
                failures.append(f"{slug}: {candidate}: {exc}")
            except Exception as exc:  # network, decode, anything
                failures.append(f"{slug}: {candidate}: {type(exc).__name__} {exc}")
        else:
            print(f"  !! {slug}: every query failed")

    if failures:
        print("\nfailures:")
        for f in failures:
            print("  -", f)
    if metas and not args.print_only:
        existing = {}
        for json_file in sorted(SRC_DIR.glob("*.json")):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if data.get("slug") and (SRC_DIR / f"{data['slug']}.json").exists():
                    existing[data["slug"]] = data
            except Exception:
                pass
        merged = {**existing, **{m["slug"]: m for m in metas}}
        write_source_index(merged)
        print(f"wrote {INDEX_FILE.relative_to(ROOT)} ({len(merged)} sources)")
    total = sum(m.get("bytes", 0) for m in metas)
    print(f"\n{len(metas)}/{len(slugs)} pieces, {len(failures)} failures, {total/1024:.0f} KB of modules")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
