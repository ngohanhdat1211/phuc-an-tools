"""Redesign: ảnh design có sẵn -> Claude nghĩ mẫu MỚI cùng ngách (câu chữ + bố cục mới) -> SVG -> PNG 4200x4800 nền trong.
Không tốn API: gọi Claude Code đã đăng nhập gói Max trên máy (trừ vào hạn mức Max).
Chạy: python tool\\redesign.py <ảnh.png | thư mục> [--so 2] [--khong-soat] [--ra <thư mục>]
Kết quả: <thư mục ảnh>\\Redesign Claude\\<câu chữ mới>.png (+ .svg để sửa tay).
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from PIL import Image

FONT = ["Anton", "Oswald:wght@400;600;700", "Bebas+Neue", "Playfair+Display:ital,wght@0,700;1,800",
        "Yellowtail", "Black+Ops+One", "Alfa+Slab+One", "Pacifico", "Permanent+Marker", "Roboto+Slab:wght@700",
        "Graduate", "Rye", "Staatliches", "Bungee", "Sancreek", "Cinzel:wght@700;900", "Kaushan+Script",
        "Lobster", "Holtwood+One+SC", "Racing+Sans+One", "Great+Vibes", "Dancing+Script:wght@700", "Satisfy",
        "Sacramento", "Allura", "Montserrat:wght@800;900", "Poppins:wght@700;800", "Abril+Fatface",
        "Bangers", "Luckiest+Guy", "Amatic+SC:wght@700", "Cookie"]
TEN_FONT = "Anton, Oswald, Bebas Neue, Playfair Display, Yellowtail, Black Ops One, Alfa Slab One, Pacifico, " \
           "Permanent Marker, Roboto Slab, Graduate, Rye, Staatliches, Bungee, Sancreek, Cinzel, Kaushan Script, " \
           "Lobster, Holtwood One SC, Racing Sans One, Great Vibes, Dancing Script, Satisfy, Sacramento, Allura, " \
           "Montserrat, Poppins, Abril Fatface, Bangers, Luckiest Guy, Amatic SC, Cookie"
DUOI = (".png", ".jpg", ".jpeg", ".webp")

# mỗi mẫu đổi BỐ CỤC, còn phong cách/khí chất giữ theo mẫu gốc
BO_CUC = [
    "illustration on one side, stacked text block on the other side (asymmetric, magazine-cover feel)",
    "hero illustration centered, big hero word above or across it, supporting lines below",
    "text-led: huge expressive hero word/lettering filling the width, illustration smaller and tucked into the text",
    "illustration at the bottom/foreground rising into the text, text arranged in a tight block on top",
]

DE_BAI = """You are an award-level t-shirt graphic designer whose designs sell in the Etsy / Amazon Merch top 1%.
Look at the reference design image: {anh}
It belongs to ANOTHER shop. Do NOT copy its wording, slogan or exact artwork. Goal: a NEW design for the SAME buyer
that is clearly better than the reference, so a buyer scrolling past 50 similar shirts stops and buys this one{khac}.

Step 1 - study the reference (silently) and KEEP its vibe. Note: target buyer (gender, age, personality), mood
(e.g. sassy/sexy/glam, funny, cute, badass, patriotic, vintage, faith...), art technique (e.g. watercolor splashes,
fashion illustration, retro, grunge, cartoon), color family, font personality (script, brush, block...).
The new design MUST feel like it belongs to the same style category and would sell to the same person:
a young sexy glam design stays young/sexy/glam (NOT vintage badges); a vintage design stays vintage; a woman-focused
design stays woman-focused (slogan written for her, feminine illustration). Upgrade quality, don't change genre.

Step 2 - slogan (2-9 words, plus an optional short supporting list like the reference has): same attitude as the
reference but new words, the buyer would say it about herself/himself. Plain English. Not a famous quote, not a
trademark, no brand/team/character/celebrity names, no "shirt/tee" words. No official military branch names, seals
or insignia.

Step 3 - layout for THIS variant: {bo_cuc}

Step 4 - draw it as a rich, professional SVG:
- NEVER draw human figures, faces or bodies (code-drawn people look stiff and cheap). If the reference shows a
  person, replace them with iconic OBJECTS/SYMBOLS of the same vibe and buyer, drawn beautifully: e.g. glam = glossy
  lips, big sunglasses with gradient lenses and shine, high heels, crown, cocktail glass with splash and garnish,
  sparkles, hoop earrings; job niches = the tools of the trade. Make the objects a rich hero illustration: many
  <path> elements with C/Q curves, at least 2 tones per object (base + shadow + highlight), gradients, glints.
- Background effects that match the vibe, e.g. watercolor/paint splashes = several overlapping irregular blobs with
  low-opacity gradients + drips + small splatter dots (make blob edges organic with
  <filter><feTurbulence baseFrequency="0.01" numOctaves="3"/><feDisplacementMap scale="120"/></filter>).
- Typography: 2-3 fonts with the same personality as the reference (script/brush for glam, block for bold),
  one hero word very large, outlines/shadows/colored glow layers for depth. Every text line uses
  textLength + lengthAdjust="spacingAndGlyphs".
- Composition: compact, balanced chest graphic, no random floating bits, no big empty gaps.
- Canvas: <svg xmlns="http://www.w3.org/2000/svg" width="4200" height="4800" viewBox="0 0 4200 4800">,
  transparent background, printed on a {nen} shirt -> colors that pop on it (as colorful as the reference). On a dark
  shirt NEVER use navy, black, dark gray or dark colors for text or large shapes (dark only as small inner details over
  light shapes); on a light shirt avoid white/cream/pale colors for text.
- Fonts: only these Google Fonts by font-family: {font}. Everything inside x 150..4050, y 150..4650, art ~90% wide.
- No raster images, no <image>, no external links.
- Distress/grunge texture ONLY if the reference is vintage/grunge. If used: <filter id="g" x="0" y="0" width="100%"
  height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.02" numOctaves="4" seed="7" result="n"/>
  <feColorMatrix in="n" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 12 -7.6" result="m"/>
  <feComposite in="SourceGraphic" in2="m" operator="out"/></filter>, never on text smaller than font-size 350.
- Write the SVG with the Write tool to: {svg}
Then answer with exactly one line: SLOGAN: <the new slogan>"""

SOAT = """You are the art director. Look at the rendered preview: {xem} (SVG source: {svg}). Background = shirt color ({nen}).
Reference design from a competitor: {anh}
Judge it like the reference's buyer on Etsy. Score 1-10 for: SAME VIBE as the reference (mood, target buyer,
art technique, font personality - a vintage badge for a glam/sexy reference scores 1), illustration quality,
typography craft, composition, color contrast on the shirt.
1) Always fix errors: clipped/overflowing text, overlaps, illegible text, weak contrast, broken or awkward art, any human figure/face (remove it, replace with objects),
   big empty gaps.
2) If any score is below 8: UPGRADE the SVG (restyle toward the reference's vibe, more detailed/elegant illustration
   with shading and highlights, better type lockup, tighter composition) - keep the same slogan.
   Rewrite the file with the Write tool.
If everything is 8+ and error-free, do not touch the file.
Answer with exactly one line: OK or FIXED"""


def tim_claude():
    p = shutil.which("claude")
    if p:
        return p
    ds = glob.glob(os.path.expanduser(r"~\.vscode\extensions\anthropic.claude-code-*\resources\native-binary\claude.exe"))
    if ds:
        return sorted(ds, key=os.path.getmtime)[-1]
    sys.exit("Không thấy Claude Code. Cài Claude Code + đăng nhập tài khoản Max trên máy này trước.")


def tim_chrome():
    for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
              os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
              r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if os.path.exists(p):
            return p
    sys.exit("Không thấy Chrome/Edge để xuất PNG.")


MO_HINH = {"model": None, "effort": None}  # đặt từ dòng lệnh: --mo-hinh sonnet --muc low


def goi_claude(claude, cau, cwd, them_thu_muc):
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)  # ép dùng tài khoản Max, không tính tiền API
    # gọn ngữ cảnh: chỉ Read/Write, không MCP/plugin/cài đặt, lời nhắc hệ thống ngắn -> tốn ít hạn mức Max
    lenh = [claude, "-p", cau, "--output-format", "json", "--tools", "Read,Write", "--allowedTools", "Read,Write",
            "--strict-mcp-config", "--setting-sources", "", "--add-dir", them_thu_muc,
            "--system-prompt", "You are a senior t-shirt graphic designer. Work only with the files named in the task."]
    if MO_HINH.get("model"):
        lenh += ["--model", MO_HINH["model"]]
    if MO_HINH.get("effort"):
        lenh += ["--effort", MO_HINH["effort"]]
    r = subprocess.run(lenh, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=900)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError((r.stderr or r.stdout)[-500:])
    if d.get("is_error"):
        raise RuntimeError(str(d.get("result"))[:500])
    if os.environ.get("RD_DEBUG"):
        print("  mo hinh:", list((d.get("modelUsage") or {}).keys()), flush=True)
    return d.get("result", ""), d.get("total_cost_usd", 0)


def ve_png(chrome, svg, png, tam):
    """SVG -> PNG 4200x4800 nền trong bằng Chrome headless (tải font Google)."""
    html = os.path.join(tam, "ve.html")
    link = "https://fonts.googleapis.com/css2?" + "&".join("family=" + f for f in FONT) + "&display=block"
    noi_dung = open(svg, encoding="utf-8").read()
    noi_dung = noi_dung[noi_dung.find("<svg"):]
    open(html, "w", encoding="utf-8").write(
        f'<!DOCTYPE html><html><head><meta charset="utf-8"><link href="{link}" rel="stylesheet">'
        f'<style>html,body{{margin:0;background:transparent}}svg{{display:block}}</style></head><body>{noi_dung}</body></html>')
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                    "--default-background-color=00000000", "--window-size=4200,4800", "--virtual-time-budget=15000",
                    f"--user-data-dir={os.path.join(tam, 'cr')}", f"--screenshot={png}",
                    "file:///" + html.replace("\\", "/")], capture_output=True, timeout=180)
    if not os.path.exists(png):
        raise RuntimeError("Chrome không xuất được PNG")


def xem_truoc(png, ra, nen):
    im = Image.open(png).convert("RGBA")
    im.thumbnail((700, 800))
    bg = Image.new("RGBA", im.size, (28, 30, 38, 255) if nen == "dark" else (245, 245, 240, 255))
    bg.alpha_composite(im)
    bg.convert("RGB").save(ra, quality=90)


def ten_file(s):
    s = re.sub(r"\s*\(.*?\)", "", s)  # bỏ dòng phụ trong ngoặc khỏi tên file
    s = re.sub(r'[\\/:*?"<>|]+', "", s).strip()
    return s[:120].rstrip(". ") or "redesign"


def nen_ao(anh):
    """Design sáng (nhiều điểm sáng) -> in áo tối."""
    im = Image.open(anh).convert("RGBA")
    im.thumbnail((300, 300))
    px = [p for p in im.convert("RGBA").get_flattened_data() if p[3] > 128] if hasattr(im, "get_flattened_data") else [p for p in im.getdata() if p[3] > 128]
    if not px:
        return "dark"
    sang = sum((p[0] + p[1] + p[2]) / 3 for p in px) / len(px)
    return "dark" if sang > 110 else "light"


def redesign(anh, ra, so=1, soat=True, claude=None, chrome=None, bao=print):
    claude, chrome = claude or tim_claude(), chrome or tim_chrome()
    os.makedirs(ra, exist_ok=True)
    nen = nen_ao(anh)
    kq, da = [], []
    lech = sum(map(ord, os.path.basename(anh))) % len(BO_CUC)  # design khác nhau bắt đầu bố cục khác
    for i in range(so):
        tam = tempfile.mkdtemp(prefix="rd_", dir=ra)
        svg = os.path.join(tam, "design.svg")
        khac = (f'. Already made: {"; ".join(da)} - the new slogan must not reuse their key words or opening words, '
                f'and the hero illustration must use different objects/scene (same vibe and buyer)') if da else ""
        t0 = time.time()
        bao(f"[{i + 1}/{so}] Claude đang nghĩ mẫu mới cho {os.path.basename(anh)}…")
        tra, phi = goi_claude(claude, DE_BAI.format(anh=os.path.abspath(anh), khac=khac, nen=nen, font=TEN_FONT,
                                                    svg=svg, bo_cuc=BO_CUC[(i + lech) % len(BO_CUC)]), tam, os.path.dirname(os.path.abspath(anh)))
        m = re.search(r"SLOGAN:\s*(.+)", tra)
        cau = m.group(1).strip().strip('"') if m else f"redesign {i + 1}"
        if not os.path.exists(svg):
            raise RuntimeError("Claude không ghi SVG: " + tra[:200])
        png = os.path.join(tam, "design.png")
        ve_png(chrome, svg, png, tam)
        if soat:
            xem = os.path.join(tam, "xem.jpg")
            xem_truoc(png, xem, nen)
            bao(f"[{i + 1}/{so}] Claude soát lại bản vẽ…")
            tra2, phi2 = goi_claude(claude, SOAT.format(xem=xem, svg=svg, nen=nen, anh=os.path.abspath(anh)), tam,
                                     os.path.dirname(os.path.abspath(anh)))
            phi += phi2
            if "FIXED" in tra2.upper():
                os.remove(png)
                ve_png(chrome, svg, png, tam)
        ten = ten_file(cau)
        dich = os.path.join(ra, ten + ".png")
        n = 2
        while os.path.exists(dich):
            dich = os.path.join(ra, f"{ten} ({n}).png")
            n += 1
        shutil.move(png, dich)
        shutil.move(svg, dich[:-4] + ".svg")
        shutil.rmtree(tam, ignore_errors=True)
        da.append(cau)
        kq.append(dich)
        bao(f"Da luu: {dich}")
        bao(f"[{i + 1}/{so}] Xong: {os.path.basename(dich)}  ({time.time() - t0:.0f}s, quy đổi ~${phi:.2f} hạn mức Max)")
    return kq


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("nguon")
    ap.add_argument("--so", type=int, default=1, help="số mẫu mới cho mỗi design")
    ap.add_argument("--khong-soat", action="store_true")
    ap.add_argument("--ra")
    ap.add_argument("--mo-hinh", help="opus | sonnet | haiku (bỏ trống = mặc định)")
    ap.add_argument("--muc", help="mức suy nghĩ: low | medium | high")
    a = ap.parse_args()
    ds = [a.nguon] if os.path.isfile(a.nguon) else sorted(
        f for f in glob.glob(os.path.join(a.nguon, "*")) if f.lower().endswith(DUOI))
    MO_HINH.update(model=a.mo_hinh, effort=a.muc)
    claude, chrome = tim_claude(), tim_chrome()
    for anh in ds:
        ra = a.ra or os.path.join(os.path.dirname(os.path.abspath(anh)), "..", "Redesign Claude") \
            if os.path.basename(os.path.dirname(os.path.abspath(anh))) == "Design Claude" \
            else (a.ra or os.path.join(os.path.dirname(os.path.abspath(anh)), "Redesign Claude"))
        try:
            redesign(anh, os.path.normpath(ra), a.so, not a.khong_soat, claude, chrome)
        except Exception as e:
            if any(k in str(e).lower() for k in ("limit", "quota", "usage")):  # hết hạn mức Max -> dừng cả loạt
                print(f"LỖI hết hạn mức Claude Max, dừng loạt. Chờ hạn mức hồi rồi chạy lại các mẫu còn lại. ({e})")
                break
            print(f"LỖI {os.path.basename(anh)}: {e}")


if __name__ == "__main__":
    main()
