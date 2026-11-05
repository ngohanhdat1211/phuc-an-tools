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
        "Yellowtail", "Black+Ops+One", "Alfa+Slab+One", "Pacifico", "Permanent+Marker", "Roboto+Slab:wght@700"]
TEN_FONT = "Anton, Oswald, Bebas Neue, Playfair Display, Yellowtail, Black Ops One, Alfa Slab One, Pacifico, " \
           "Permanent Marker, Roboto Slab"
DUOI = (".png", ".jpg", ".jpeg", ".webp")

DE_BAI = """You are a senior t-shirt graphic designer for an Etsy/Amazon Merch shop.
Look at the reference design image: {anh}
It belongs to ANOTHER shop. Do NOT copy its wording, slogan, layout or artwork. Keep only the niche and the buyer
(who wears it, what they are proud of). Invent ONE new, original, more striking design for the same buyers{khac}.

Rules:
- New short slogan (2-9 words), punchy, emotional or funny, plain English. Not a famous quote, not a trademark,
  no brand/team/character names, no "shirt/tee" words.
- Strong typographic hierarchy (one hero word/line), plus simple vector art built from shapes/paths
  (badges, flags, stars, sunsets, mountains, tools, frames, ribbons). No raster images, no <image>, no external links.
- Canvas: <svg xmlns="http://www.w3.org/2000/svg" width="4200" height="4800" viewBox="0 0 4200 4800">,
  transparent background, printed on a {nen} shirt -> choose colors that pop on it (max 4 colors). On a dark shirt NEVER use navy, black, dark gray or any dark color
  for text or large shapes (they disappear); on a light shirt avoid white/cream/pale colors.
- Fonts: only these Google Fonts by font-family: {font}. Use textLength + lengthAdjust="spacingAndGlyphs" on wide
  lines so text never overflows. Keep everything inside x 150..4050, y 150..4650. Fill the canvas well (art ~ 90% wide).
- Optional vintage distress: wrap content in <g filter="url(#g)"> with
  <filter id="g" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency="0.02"
  numOctaves="4" seed="7" result="n"/><feColorMatrix in="n" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 12 -7.6"
  result="m"/><feComposite in="SourceGraphic" in2="m" operator="out"/></filter>
  Never put the distress filter on text smaller than font-size 350 (it eats letters) - keep small text outside it.
- Write the SVG with the Write tool to: {svg}
Then answer with exactly one line: SLOGAN: <the new slogan>"""

SOAT = """Check the rendered preview of your design: {xem} (SVG source: {svg}). The preview background is the shirt color ({nen}).
Fix any problem by rewriting the SVG file with the Write tool: text clipped/overflowing, overlapping elements,
illegible text, any text or shape with weak contrast against the shirt color, unbalanced empty space, art that looks broken. If it is already good, do not touch the file.
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


def goi_claude(claude, cau, cwd, them_thu_muc):
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)  # ép dùng tài khoản Max, không tính tiền API
    # gọn ngữ cảnh: chỉ Read/Write, không MCP/plugin/cài đặt, lời nhắc hệ thống ngắn -> tốn ít hạn mức Max
    lenh = [claude, "-p", cau, "--output-format", "json", "--tools", "Read,Write", "--allowedTools", "Read,Write",
            "--strict-mcp-config", "--setting-sources", "", "--add-dir", them_thu_muc,
            "--system-prompt", "You are a senior t-shirt graphic designer. Work only with the files named in the task."]
    r = subprocess.run(lenh, cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8", timeout=900)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError((r.stderr or r.stdout)[-500:])
    if d.get("is_error"):
        raise RuntimeError(str(d.get("result"))[:500])
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
    for i in range(so):
        tam = tempfile.mkdtemp(prefix="rd_", dir=ra)
        svg = os.path.join(tam, "design.svg")
        khac = f'. Already made (do something clearly different): {"; ".join(da)}' if da else ""
        t0 = time.time()
        bao(f"[{i + 1}/{so}] Claude đang nghĩ mẫu mới cho {os.path.basename(anh)}…")
        tra, phi = goi_claude(claude, DE_BAI.format(anh=os.path.abspath(anh), khac=khac, nen=nen, font=TEN_FONT,
                                                    svg=svg), tam, os.path.dirname(os.path.abspath(anh)))
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
            tra2, phi2 = goi_claude(claude, SOAT.format(xem=xem, svg=svg, nen=nen), tam, tam)
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
    a = ap.parse_args()
    ds = [a.nguon] if os.path.isfile(a.nguon) else sorted(
        f for f in glob.glob(os.path.join(a.nguon, "*")) if f.lower().endswith(DUOI))
    claude, chrome = tim_claude(), tim_chrome()
    for anh in ds:
        ra = a.ra or os.path.join(os.path.dirname(os.path.abspath(anh)), "..", "Redesign Claude") \
            if os.path.basename(os.path.dirname(os.path.abspath(anh))) == "Design Claude" \
            else (a.ra or os.path.join(os.path.dirname(os.path.abspath(anh)), "Redesign Claude"))
        try:
            redesign(anh, os.path.normpath(ra), a.so, not a.khong_soat, claude, chrome)
        except Exception as e:
            print(f"LỖI {os.path.basename(anh)}: {e}")


if __name__ == "__main__":
    main()
