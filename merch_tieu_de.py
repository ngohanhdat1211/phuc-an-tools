r"""Viết Title / Brand / 2 Bullet cho Amazon Merch on Demand từ ảnh design.

- Đọc chữ trên design (RapidOCR, chạy máy, không tốn tiền) + gợi ý từ tên file.
- Từ khoá: ô gợi ý tìm kiếm Amazon (khách thật gõ), lưu đệm 14 ngày; mất mạng thì dùng bộ dựng sẵn.
- Bullet/mô tả rải cụm khách gõ thật (bỏ chữ loại hàng), mỗi design một kiểu câu.
- Soát độ dài Merch: Title <=60, Brand <=50, Bullet <=256; từ cấm theo nhóm (thương hiệu, người nổi tiếng,
  công dụng y tế, thù ghét, lời quảng cáo). Cột uspto = link tra câu chữ design; ban_quyen để Claude soát.

Chạy:
  python merch_tieu_de.py anh.png                 -> in ra màn hình
  python merch_tieu_de.py "<thư mục design>"      -> <thư mục>\_MERCH.csv (mở bằng Excel)
  --nganh "Electrician"   đặt tên nghề (mặc định đoán từ tên thư mục)
  --brand "Ten Brand"     dùng 1 brand cố định
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

GOC = os.path.dirname(os.path.abspath(__file__))
TAM = os.path.join(os.path.dirname(GOC), "tam")
if not os.path.isdir(TAM):
    TAM = os.path.join(GOC, "tam")
DEM = os.path.join(TAM, "merch_tu_khoa.json")
DUOI_ANH = (".png", ".jpg", ".jpeg", ".webp")

TITLE_MAX, BRAND_MAX, BULLET_MAX, MO_TA_MAX = 60, 50, 256, 2000

# Merch tự gắn loại sản phẩm -> không nhét chữ áo vào title
TU_SAN_PHAM = {"shirt", "shirts", "tshirt", "tshirts", "t-shirt", "t-shirts", "tee", "tees", "t", "hoodie",
               "hoodies", "sweatshirt", "sweatshirts", "tank", "top", "apparel", "clothing", "socks", "hat",
               "hats", "mug", "mugs", "sticker", "stickers", "decal", "jacket", "long", "sleeve", "v-neck"}
TU_NOI = {"i", "i'm", "im", "a", "an", "the", "of", "my", "is", "to", "and", "with", "in", "on", "it", "that",
          "this", "be", "you", "your", "me", "what", "do", "at", "by", "or", "are", "if", "not", "near", "under"}
# Từ cấm theo nhóm. Danh sách mồi — câu chữ design vẫn phải tra USPTO + skill soat-ban-quyen trước khi đăng.
# Chỉ để tên riêng dễ nhận; từ thông dụng trùng tên hãng (dodge, vans, craftsman, giants...) bỏ ra để khỏi báo nhầm.
NHOM_CAM = {
    "từ thương hiệu": [
        "disney", "marvel", "pixar", "star wars", "harry potter", "hogwarts", "pokemon", "hello kitty", "barbie",
        "lego", "nike", "adidas", "under armour", "the north face", "patagonia", "levi's", "levis", "crocs",
        "gucci", "louis vuitton", "chanel", "playboy", "nfl", "nba", "mlb", "nhl", "ncaa", "nascar", "wwe", "ufc",
        "pga", "fifa", "espn", "super bowl", "olympic", "olympics", "coca cola", "coca-cola", "pepsi", "starbucks",
        "dunkin", "mcdonald's", "mcdonalds", "red bull", "monster energy", "mountain dew", "budweiser", "busch",
        "coors", "jack daniels", "jack daniel's", "fireball", "tito's", "minecraft", "fortnite", "roblox",
        "mickey", "minnie", "snoopy", "peanuts gang", "garfield", "spongebob", "sesame street", "looney tunes",
        "scooby", "batman", "superman", "spider-man", "spiderman", "avengers", "punisher", "grinch", "bluey",
        "jurassic park", "star trek", "game of thrones", "stranger things", "grey's anatomy", "yellowstone",
        "duck dynasty", "netflix", "yeti", "stanley", "carhartt", "harley", "harley-davidson", "jeep", "ford",
        "chevy", "chevrolet", "ferrari", "porsche", "tesla", "john deere", "kubota", "dewalt", "milwaukee",
        "snap-on", "makita", "ryobi", "stihl", "husqvarna", "klein tools", "lincoln electric", "realtree",
        "mossy oak", "glock", "remington", "boy scouts", "girl scouts", "amazon", "prime",
        "kansas city chiefs", "packers", "steelers", "49ers", "seahawks", "buccaneers", "dallas cowboys",
        "new england patriots", "yankees", "dodgers", "red sox", "lakers", "celtics",
    ],
    "người nổi tiếng/chính trị": [
        "taylor swift", "beyonce", "elvis", "marilyn monroe", "michael jordan", "air jordan", "lebron",
        "dolly parton", "trump", "biden", "kamala", "obama", "maga", "let's go brandon", "lets go brandon",
    ],
    "công dụng y tế": ["cure", "cures", "heals", "fda", "covid", "vaccine", "prevents", "anti-anxiety"],
    "thù ghét": ["nazi", "kkk", "swastika", "white power"],
}
TU_CAM = [t for ds in NHOM_CAM.values() for t in ds]
TU_QUANG_CAO = ["best seller", "bestseller", "best selling", "sale", "discount", "free shipping",
                "limited time", "#1", "100%", "guarantee", "top rated", "official", "licensed"]

# Từ khoá dựng sẵn khi không gọi được Amazon (kiểu khách hay gõ cho áo nghề)
TU_KHOA_SAN = ["funny", "gifts", "for men", "for women", "dad", "humor", "sarcastic", "retirement",
               "appreciation", "proud", "christmas", "birthday"]
MAU_GIU_HOA = {"cna", "emt", "hvac", "rn", "lpn", "usa", "us", "ems", "dad", "mom"}


# ---------------- nghề ----------------
def doan_nganh(duong):
    """Tên nghề từ thư mục: 'Firefighter US 8 Design' -> 'Firefighter'; 'Design CNA' -> 'CNA'."""
    p = os.path.abspath(duong)
    ten = os.path.basename(p if os.path.isdir(p) else os.path.dirname(p))
    ten = re.sub(r"(?i)\bdesign(s)?\b|\bclaude\b|\bus\s*\d+\b|\d+", " ", ten)
    ten = re.sub(r"\s+", " ", ten).strip(" -_")
    return chu_hoa(ten) if ten else ""


def so_nhieu(n):
    w = n.split()
    if not w:
        return n
    c = w[-1]
    if c.isupper():
        c += "s"
    elif re.search(r"(s|x|ch|sh)$", c, re.I):
        c += "es"
    elif re.search(r"[^aeiou]y$", c, re.I):
        c = c[:-1] + "ies"
    else:
        c += "s"
    return " ".join(w[:-1] + [c])


def chu_hoa(s):
    """Title Case kiểu Amazon: viết hoa đầu mỗi từ; chỉ giữ HOA cho từ viết tắt (CNA, EMT, HVAC, USA)."""
    ra = []
    for w in s.split():
        lw = w.lower().strip(".,!?\"'")
        if lw in MAU_GIU_HOA and lw not in ("dad", "mom"):
            ra.append(w.upper())
        elif w[:1] in "'\"":
            ra.append(w[:1] + w[1:2].upper() + w[2:].lower())
        else:
            ra.append(w[:1].upper() + w[1:].lower())
    return " ".join(ra)


# ---------------- đọc chữ ----------------
_ocr = None
_tu_dien = None


def tu_dien():
    """(SpellChecker sửa 1 ký tự, bảng tần suất từ). Thiếu thư viện -> (None, {})."""
    global _tu_dien
    if _tu_dien is None:
        try:
            from spellchecker import SpellChecker
            sc = SpellChecker(distance=1)
            _tu_dien = (sc, dict(sc.word_frequency.dictionary))
        except ImportError:
            _tu_dien = (None, {})
    return _tu_dien


def _tach_dinh(w, tan):
    """'istopwhen' -> ['i','stop','when'] nếu tách được hết thành từ có nghĩa."""
    import math
    n = len(w)
    tot = [(0.0, [])] + [None] * n
    for i in range(1, n + 1):
        for j in range(max(0, i - 15), i):
            m = w[j:i]
            if tot[j] is None or m not in tan or (len(m) == 1 and m not in ("a", "i")):
                continue
            c = tot[j][0] - math.log(tan[m] + 1) + 8  # +8: phạt mỗi từ, ưu tiên ít mảnh
            if tot[i] is None or c < tot[i][0]:
                tot[i] = (c, tot[j][1] + [m])
    return tot[n][1] if tot[n] else None


def sua_chu(chu, nganh=""):
    """Sửa lỗi OCR từng từ: giữ từ đúng, kéo về tên nghề, tách chữ dính, sửa 1 ký tự."""
    import difflib
    sc, tan = tu_dien()
    if not tan:
        return chu
    nghe = [w.lower() for w in nganh.split()] + [so_nhieu(w).lower() for w in nganh.split()]
    ra = []
    for tok in chu.split():
        m = re.match(r"^([^A-Za-z']*)([A-Za-z'.]+?)([^A-Za-z']*)$", tok)
        if not m:
            ra.append(tok)
            continue
        dau, w, duoi = m.groups()
        lw = w.lower().strip(".")
        moi = w
        gan = [n for n in nghe if difflib.SequenceMatcher(None, lw, n).ratio() >= 0.72]
        if lw in tan or lw in nghe or len(lw) <= 2:
            moi = w
        elif gan:
            moi = gan[0]
        else:
            tach = _tach_dinh(lw.replace("'", ""), tan) if len(lw) >= 5 else None
            if tach and len(tach) <= 4:
                moi = " ".join(tach)
            elif sc is not None:
                c = sc.correction(lw)
                moi = c if c else w
        if moi.lower() != w.lower() and w.isupper():
            moi = moi.upper()
        ra.append(dau + moi + duoi)
    return " ".join(ra)


def _ti_le_tu_that(dong):
    _, tan = tu_dien()
    tu = [w.lower().strip(".,!?'\"") for d in dong for w in d[2].split()]
    tu = [w for w in tu if w]
    if not tan or not tu:
        return sum(len(d[2]) * d[3] for d in dong)
    return sum(len(w) for w in tu if w in tan) + 0.3 * sum(len(w) for w in tu)


def doc_chu(duong, nganh=""):
    """Các dòng chữ trên design, trên xuống dưới: [(chữ, độ tin, cao chữ px)]. Đọc trên nền trắng + đen, giữ bản tốt hơn."""
    global _ocr
    import numpy as np
    from PIL import Image
    if _ocr is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr = RapidOCR()
    im = Image.open(duong).convert("RGBA")
    im.thumbnail((1400, 1600))
    tot = []
    for nen in ((255, 255, 255), (0, 0, 0)):
        b = Image.new("RGBA", im.size, nen + (255,))
        b.alpha_composite(im)
        kq, _ = _ocr(np.asarray(b.convert("RGB")))
        dong = []
        for hop, chu, tin in kq or []:
            tin = float(tin)
            chu = re.sub(r"\s+", " ", str(chu)).strip()
            if tin < 0.7 or len(re.sub(r"[^A-Za-z]", "", chu)) < 2:
                continue
            y = sum(p[1] for p in hop) / 4
            x = sum(p[0] for p in hop) / 4
            cao = abs(hop[3][1] - hop[0][1])
            dong.append((y, x, chu, tin, cao))
        if _ti_le_tu_that(dong) > _ti_le_tu_that(tot):
            tot = dong
    # xếp theo hàng (cùng hàng nếu lệch y ít), trong hàng trái -> phải
    tot.sort()
    hang, ra = [], []
    for d in tot:
        if hang and abs(d[0] - hang[-1][0]) > 25:
            ra += sorted(hang, key=lambda x: x[1])
            hang = []
        hang.append(d)
    ra += sorted(hang, key=lambda x: x[1])
    return [(sua_chu(d[2], nganh), round(d[3], 2), round(d[4])) for d in ra]


def chu_tu_ten_file(duong):
    """Gợi ý từ tên file mockup: 'Always to be nice to Electricians- Black -Electrician- T-shirt -#...'"""
    t = os.path.splitext(os.path.basename(duong))[0]
    t = re.split(r"#", t)[0]
    t = re.sub(r"(?i)-?image-\d+|\(\d+\)", " ", t)
    manh = [m.strip() for m in re.split(r"\s[-_|]\s|-(?=\s)|(?<=\s)-|_", t) if m.strip()]
    mau = {"black", "white", "navy", "grey", "gray", "red", "blue", "green", "pink", "purple", "maroon",
           "charcoal", "sand", "orange", "yellow", "brown", "heather"}
    ra = []
    for m in manh:
        tu = [w for w in re.findall(r"[A-Za-z']+", m)]
        if not tu or all(w.lower() in TU_SAN_PHAM | mau for w in tu):
            continue
        ra.append(" ".join(w for w in m.split() if w.lower().strip("-") not in TU_SAN_PHAM))
    return [r for r in ra if len(r) > 3]


def chu_chinh(dong, toi_da=40, nganh=""):
    """Câu chính = dòng chữ to (headline) theo thứ tự đọc; bỏ số thứ tự, mảnh vỡ tên nghề ('Elect1')."""
    nghe = [w.lower() for w in nganh.split()]
    sach = []
    for d in dong:
        tu = [w for w in d[0].split() if not re.search(r"[A-Za-z]\d|\d[A-Za-z]|^\d+[.)]?$", w)
              and not any(n.startswith(w.lower().strip(".")) and len(w) < len(n) for n in nghe if len(w) >= 3)]
        if tu:
            sach.append((" ".join(tu), d[2] if len(d) > 2 else 1))
    if not sach:
        return ""
    to = max(c for _, c in sach)
    chon = [c for c, h in sach if h >= 0.6 * to]
    if len(" ".join(chon)) < 12:  # headline quá ngắn: thêm các dòng kế tiếp
        chon = [c for c, _ in sach]
    cau = ""
    for c in chon:
        thu = (cau + " " + c).strip()
        if len(thu) > toi_da:
            break
        cau = thu
    return chu_hoa(cau or chon[0][:toi_da])


def chon_chu(dong, ten, nganh=""):
    """Chữ chính: tên file mockup thường ghi đủ câu design ('American by Birth, Concrete Finisher by Choice').
    Dùng câu tên file khi nó chứa >=60% từ OCR đọc được (chữ >=3 ký tự); không thì lấy headline OCR."""
    ocr = chu_chinh(dong, nganh=nganh)
    tu_ocr = {w for d in dong for w in re.findall(r"[a-z']{3,}", d[0].lower())}
    tot, diem_tot = "", 0.0
    for t in ten or []:
        t = re.sub(r"\s+", " ", t).strip(" ,.-")
        tu_t = set(re.findall(r"[a-z']{3,}", t.lower()))
        if not tu_ocr or not tu_t or len(t) > 70:
            continue
        diem = len(tu_ocr & tu_t) / len(tu_ocr)
        if diem >= 0.6 and diem > diem_tot and len(t) > len(ocr):
            tot, diem_tot = t, diem
    return chu_hoa(tot) if tot else ocr


# Kiểu design đoán từ chữ: hài hước / tự hào (yêu nước) / trung tính.
# Amazon xếp "funny" cao cho mọi nghề, nhưng gắn funny cho design nghiêm túc = khách tìm hài thấy không hợp -> không bấm.
DAU_HAI = ["because", "badass", "accident", "therapy", "nobody", "coffee", "beer", "wine", "drink", "sarcas",
           "funny", "joke", "humor", "lol", "don't", "dont", "hourly rate", "trust me", "warning", "caution",
           "i'm not", "im not", "assume", "shit", "hell", "damn", "crazy", "weird", "nap", "lazy", "ask me",
           "i paused", "survived", "make it look", "kinda", "probably", "i fix", "if you", "you can't",
           "older", "old man", "grumpy", "spoiler", "nope", "oops", "what part of", "may contain", "level",
           "loading", "retirement plan", "zombie", "happy hour", "excuse", "my wife", "?"]
DAU_HAO = ["american", "america", "usa", "u.s.a", "flag", "freedom", "patriot", "proud", "pride", "honor",
           "veteran", "brave", "by birth", "by choice", "legend", "built", "strong", "hardworking",
           "hard working", "union", "skilled", "god", "faith", "blessed", "respect", "dedicat", "heart", "soul",
           "blood", "sweat", "grit", "tough", "born", "since", "we the people", "land of", "home of", "hero"]
DAU_YEU_NUOC = ["american", "america", "usa", "u.s.a", "flag", "freedom", "patriot", "we the people",
                "land of", "home of", "veteran"]
GIONG_TEN = {"hai": "Hài hước", "hao": "Tự hào / yêu nước", "trung": "Trung tính"}
TU_HAI = {"funny", "humor", "humorous", "sarcastic", "joke", "pun", "novelty", "gag"}
TU_HAO = {"proud", "pride", "patriotic", "american", "usa", "flag"}


def _dau(c, ds):
    return [d for d in ds if (d in c if (" " in d or not d.isalpha()) else re.search(r"(?<![a-z])" + d, c))]


# ---------------- Claude Opus nhìn ảnh (gói Max qua Claude Code, không tốn API) ----------------
TEP_CLAUDE = "_merch_claude.json"  # đệm kết quả trong thư mục design: không đọc lại ảnh đã đọc
DE_CLAUDE = """You are a senior Amazon Merch on Demand lister. Read every image file listed below (t-shirt designs,{nganh}).
For EACH image decide:
- giong: the design's tone for the listing title. "hai" = funny, sarcastic, joke, pun, gag. "hao" = proud, patriotic,
  sentimental, honor, tribute, inspirational. "trung" = neutral/plain (just a name, a profession, a simple statement).
  Judge the message a buyer gets from the whole design (words + art), not single words. American flag + "by birth,
  by choice" = hao. A sarcastic line over a flag is still hai.
- chu: the main printed text exactly as a buyer reads it, in natural order, Title Case, no line breaks. Skip tiny
  watermarks / shop logos. If the text is unreadable, use the file name wording.
- chu_ngan: the shortest phrase (max 40 characters) a shopper would search that names this design, taken from its
  words, e.g. "Concrete Finisher's Wife", "Welding Is My Therapy", "American By Birth Welder By Choice".
- gioi: who the design is worn by / bought for. "nu" = woman (wife, mom, girlfriend, she/her...), "nam" = man
  (dad, husband, grandpa, he/him as the wearer...), "ca" = anyone. Note: a wife's design that talks about "he" is "nu".
- dau: 2-4 short English visual cues that justify giong.
- ly_do: one short sentence in Vietnamese explaining the tone.
- rui_ro: anything that can get the listing removed on Amazon: brand names or logos, sports teams, characters,
  celebrities, politicians, military branch official seals/insignia, famous trademarked slogans. Empty list if none.
Answer ONLY a JSON array, one object per image, same order:
[{{"file":"<file name>","giong":"hai|hao|trung","chu":"...","chu_ngan":"...","gioi":"nam|nu|ca","dau":["..."],
  "ly_do":"...","rui_ro":["..."]}}]
Images:
{anh}"""


def tim_claude():
    """claude.exe của Claude Code (PATH hoặc extension VS Code). Không có -> None."""
    import glob
    import shutil
    p = shutil.which("claude")
    if p:
        return p
    ds = glob.glob(os.path.expanduser(r"~\.vscode\extensions\anthropic.claude-code-*\resources\native-binary\claude.exe"))
    return sorted(ds, key=os.path.getmtime)[-1] if ds else None


def _dem_claude(thu_muc):
    try:
        return json.load(open(os.path.join(thu_muc, TEP_CLAUDE), encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def nap_claude(anh):
    """Kết quả Claude đã đọc cho 1 ảnh (còn khớp ngày sửa file) hoặc None."""
    r = _dem_claude(os.path.dirname(anh)).get(os.path.basename(anh))
    if r and abs(r.get("mtime", 0) - os.path.getmtime(anh)) < 2:
        return r
    return None


def _ghi_dem_claude(thu_muc, moi):
    d = _dem_claude(thu_muc)
    d.update(moi)
    tep = os.path.join(thu_muc, TEP_CLAUDE)
    with open(tep + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    os.replace(tep + ".tmp", tep)


def _goi_claude_anh(claude, anh, nganh, mo_hinh="opus"):
    import subprocess
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)  # ép dùng tài khoản Max, không tính tiền API
    cau = DE_CLAUDE.format(nganh=f" profession: {nganh}" if nganh else "", anh="\n".join(anh))
    lenh = [claude, "-p", cau, "--output-format", "json", "--model", mo_hinh, "--tools", "Read",
            "--allowedTools", "Read", "--strict-mcp-config", "--setting-sources", "",
            "--system-prompt", "You classify t-shirt designs for Amazon Merch. Read only the named image files."]
    for t in dict.fromkeys(os.path.dirname(a) for a in anh):
        lenh += ["--add-dir", t]
    r = subprocess.run(lenh, cwd=os.path.dirname(anh[0]), env=env, capture_output=True, text=True,
                       encoding="utf-8", timeout=900, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        d = json.loads(r.stdout)
    except ValueError:
        raise RuntimeError((r.stderr or r.stdout or "Claude không trả lời")[-300:])
    if d.get("is_error"):
        raise RuntimeError(str(d.get("result"))[:300])
    tra = d.get("result", "")
    m = re.search(r"\[.*\]", tra, re.S)
    if not m:
        raise RuntimeError("Claude trả lời không đúng dạng: " + tra[:200])
    return json.loads(m.group(0)), list((d.get("modelUsage") or {}).keys())


def chu_claude(x):
    """Chữ chính cho title từ kết quả Claude: câu đủ nếu vừa title (<=54), dài hơn thì câu ngắn."""
    c, n = x.get("chu", ""), x.get("chu_ngan", "")
    return c if c and len(c) <= TITLE_MAX - 6 else (n or c)


def doc_claude(ds_anh, nganh="", lo=4, bao=print, mo_hinh="opus", lam_lai=False):
    """Claude (mặc định Opus) nhìn từng ảnh: kiểu design, chữ chính, rủi ro thương hiệu. Lưu đệm cạnh ảnh.
    Trả {đường ảnh: kết quả}. Ảnh đã đọc (đệm còn khớp) thì bỏ qua trừ khi lam_lai."""
    claude = tim_claude()
    if not claude:
        raise RuntimeError("Máy này chưa có Claude Code (đăng nhập gói Max) — cài rồi thử lại.")
    ra = {}
    can = []
    for a in ds_anh:
        r = None if lam_lai else nap_claude(a)
        if r:
            ra[a] = r
        else:
            can.append(a)
    for i in range(0, len(can), lo):
        nhom = can[i:i + lo]
        bao(f"Claude đang xem {i + 1}-{i + len(nhom)} / {len(can)}...")
        kq, mh = _goi_claude_anh(claude, nhom, nganh, mo_hinh)
        theo_ten = {os.path.basename(str(x.get("file", ""))).lower(): x for x in kq if isinstance(x, dict)}
        moi = {}
        for j, a in enumerate(nhom):
            x = theo_ten.get(os.path.basename(a).lower()) or (kq[j] if j < len(kq) and isinstance(kq[j], dict) else None)
            if not x or x.get("giong") not in GIONG_TEN:
                continue
            x = {"giong": x["giong"], "chu": re.sub(r"\s+", " ", str(x.get("chu", ""))).strip(),
                 "chu_ngan": re.sub(r"\s+", " ", str(x.get("chu_ngan", ""))).strip()[:60],
                 "gioi": x.get("gioi") if x.get("gioi") in ("nam", "nu", "ca") else "ca",
                 "dau": [str(t) for t in (x.get("dau") or [])][:4], "ly_do": str(x.get("ly_do", "")),
                 "rui_ro": [str(t) for t in (x.get("rui_ro") or []) if str(t).strip()],
                 "mo_hinh": ",".join(mh), "mtime": os.path.getmtime(a)}
            moi.setdefault(os.path.dirname(a), {})[os.path.basename(a)] = x
            ra[a] = x
        for t, m in moi.items():
            _ghi_dem_claude(t, m)
    return ra


def doan_giong(chu, ocr=""):
    """Trả (kiểu, danh sách dấu hiệu). Đếm dấu hiệu chữ hài vs chữ tự hào trong câu design + chữ OCR."""
    c = " " + (chu + " " + (ocr or "")).lower() + " "
    hai, hao = _dau(c, DAU_HAI), _dau(c, DAU_HAO)
    if len(hai) > len(hao) or (hai and len(hai) == len(hao)):
        return "hai", hai
    if hao:
        return "hao", hao
    return "trung", []


def tk_theo_giong(tk, giong, chu=""):
    """Hài: bỏ proud/patriotic, đảm bảo có funny. Tự hào: bỏ chữ hài, thêm proud (+ patriotic nếu yêu nước).
    Trung tính: bỏ chữ hài."""
    tk = list(tk)
    if giong == "hai":
        tk = [w for w in tk if w not in ("proud", "pride", "patriotic")]
        if not TU_HAI & set(tk):
            tk.insert(min(1, len(tk)), "funny")
        return tk
    tk = [w for w in tk if w not in TU_HAI]
    if giong == "hao":
        if _dau(" " + chu.lower() + " ", DAU_YEU_NUOC) and "patriotic" not in tk:
            tk.insert(min(1, len(tk)), "patriotic")
        if "proud" not in tk:
            tk.insert(min(2, len(tk)), "proud")
    return tk


# ---------------- từ khoá Amazon ----------------
def _goi_y(prefix, alias="aps"):
    """Ô gợi ý Amazon Mỹ. alias=fashion chỉ trả 1-3 câu, aps (mọi ngành) trả 10 (đo 05/11/2026)."""
    url = ("https://completion.amazon.com/api/2017/suggestions?mid=ATVPDKIKX0DER&limit=11&alias=" + alias
           + "&prefix=" + urllib.parse.quote(prefix))
    req = urllib.request.Request(url, headers={"User-Agent": "EtsyDesignTool/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return [s["value"] for s in json.load(r).get("suggestions", [])]


def goi_y_amazon(nganh, lam_moi=False):
    """Câu khách gõ trên Amazon quanh nghề này. Lưu đệm 14 ngày. Trả (danh sách câu, nguồn)."""
    k = nganh.lower()
    dem = {}
    if os.path.exists(DEM):
        try:
            dem = json.load(open(DEM, encoding="utf-8"))
        except (OSError, ValueError):
            dem = {}
    if not lam_moi and k in dem and dem[k].get("ban") == 3 and time.time() - dem[k]["luc"] < 14 * 86400:
        return dem[k]["cau"], "amazon (đệm)"
    tien_to = [k, k + " shirt", "funny " + k, k + " gifts", k + " gifts for", k + " shirt for",
               k + " t shirt", k + " hoodie", k + " shirt funny", "retired " + k, k + " dad", k + " mom",
               k + " appreciation", k + " christmas", "proud " + k, "patriotic " + k, "american " + k]
    cau = []
    loi = 0
    for p in tien_to:
        try:
            for s in _goi_y(p, "fashion") + _goi_y(p, "aps"):
                if s not in cau:
                    cau.append(s)
        except Exception:
            loi += 1
            if loi >= 3:
                break
        time.sleep(0.25)
    if not cau:
        return [], "dựng sẵn (không gọi được Amazon)"
    dem[k] = {"luc": time.time(), "cau": cau, "ban": 3}
    os.makedirs(TAM, exist_ok=True)
    tmp = DEM + ".tmp"
    json.dump(dem, open(tmp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    os.replace(tmp, DEM)
    return cau, "amazon"


NGU_CANH = {"shirt", "shirts", "tshirt", "tshirts", "t", "tee", "tees", "gift", "gifts", "funny", "hoodie",
            "hoodies", "sweatshirt", "retired", "retirement", "appreciation", "christmas", "birthday", "humor",
            "sarcastic", "proud", "dad", "mom", "wife", "husband", "life", "patriotic", "american"}
CHO_AI = {"men", "women", "him", "her", "dad", "mom", "husband", "wife", "grandpa", "grandma"}
TU_RAC = {"teen", "boys", "girls", "kids", "toddler", "baby", "youth", "tester", "tool", "tools", "kit",
          "bag", "belt", "pouch", "pants", "boots", "gloves", "socks", "book", "books", "card", "cards",
          "ornament", "tumbler", "cup", "keychain", "near", "jobs", "job", "salary", "course", "license",
          "small", "large", "xl", "xxl", "3x", "pack", "black", "white", "blue", "red", "gray", "grey"}


# Chỉ nhận từ bổ nghĩa kiểu áo quà tặng; thứ tự do Amazon xếp (câu khách gõ nhiều đứng trước)
TU_DUOC = {"funny", "gifts", "for men", "for women", "for him", "for her", "for dad", "for mom", "dad", "mom",
           "wife", "husband", "grandpa", "retired", "retirement", "appreciation", "christmas", "birthday",
           "humor", "humorous", "sarcastic", "proud", "life", "week", "vintage", "retro", "cute", "novelty",
           "graduation", "future", "student", "squad", "crew", "team", "pride", "american", "patriotic",
           "halloween", "thanksgiving", "valentines", "fathers", "mothers", "day", "joke", "pun", "saying",
           "quote", "quotes", "sayings", "awesome", "cool", "badass", "skull", "flag", "usa"}


def tu_khoa(nganh, cau):
    """Xếp hạng từ bổ nghĩa (funny, gifts, for men...) theo số lần xuất hiện trong gợi ý Amazon."""
    bo = set(nganh.lower().split()) | {w + "s" for w in nganh.lower().split()} | {so_nhieu(nganh).lower()}
    diem = {}
    for i, c in enumerate(cau):
        tu = re.findall(r"[a-z']+", c.lower())
        if not NGU_CANH & set(tu):  # gợi ý về dụng cụ, việc làm... không phải áo -> bỏ
            continue
        j = 0
        while j < len(tu):
            w = tu[j]
            if w == "for" and j + 1 < len(tu):
                if tu[j + 1] in CHO_AI:
                    w = "for " + tu[j + 1]
                j += 1
            j += 1
            if w in bo or w not in TU_DUOC:
                continue
            w = {"gift": "gifts", "men's": "for men", "mens": "for men", "women's": "for women",
                 "womens": "for women"}.get(w, w)
            diem[w] = diem.get(w, 0) + 1 + 1.0 / (1 + i * 0.1)
    for i, w in enumerate(TU_KHOA_SAN):  # luôn có mặt, đứng sau từ Amazon thật
        diem.setdefault(w, 0.5 - i * 0.01)
    return [w for w, _ in sorted(diem.items(), key=lambda x: -x[1])]


# Từ được phép trong cụm từ khoá đưa vào bullet (ngoài tên nghề + TU_DUOC): chặn tên hãng, đồ nghề lọt vào
TU_CUM = {"for", "a", "and", "the", "gift", "gifts", "men", "women", "him", "her", "new", "male", "female",
          "coworker", "coworkers", "boss", "friend", "son", "daughter", "grandma", "nana", "papa", "father",
          "mother", "lover", "lovers", "gag", "work", "of", "year", "first"}
NAM = {"for men", "for him", "for dad", "for husband", "for grandpa", "dad", "husband", "grandpa", "male", "papa", "father", "son"}
NU = {"for women", "for her", "for mom", "for wife", "for grandma", "mom", "wife", "grandma", "nana", "female", "mother", "daughter"}


DIP_LE = {"christmas", "halloween", "thanksgiving", "valentines", "easter", "graduation"}


def _token(tu):
    """Gộp 'for X' thành một từ như tu_khoa() làm."""
    ra, j = [], 0
    while j < len(tu):
        if tu[j] == "for" and j + 1 < len(tu) and tu[j + 1] in CHO_AI:
            ra.append("for " + tu[j + 1])
            j += 2
        else:
            ra.append(tu[j])
            j += 1
    return ra


def cum_tu_khoa(nganh, cau, tk=None, nu=None, toi_da=8):
    """Cụm khách gõ thật (giữ thứ tự Amazon) đã bỏ chữ loại hàng, chỉ gồm từ an toàn, hợp giới tính và từ khoá đang tick.
    Trả [(cụm, loại)] — loại 'qua' (có gift), 'nguoi' (tận cùng bằng nghề/người), 'dip' (mở đầu bằng dịp lễ)."""
    ng = nganh.lower().split()
    if not ng:
        return []
    duoi_nghe = {ng[-1], ng[-1] + "s", so_nhieu(nganh).lower().split()[-1]}
    cho = set(ng) | duoi_nghe | TU_DUOC | TU_CUM | CHO_AI
    tk_set = set(tk) if tk is not None else None
    ra, da = [], set()
    for c in cau:
        tu = re.findall(r"[a-z']+", c.lower().replace("t shirt", "tshirt").replace("t-shirt", "tshirt"))
        if not NGU_CANH & set(tu) or not (duoi_nghe & set(tu)):
            continue
        giu, hong = [], False
        for j, w in enumerate(tu):
            if w in TU_SAN_PHAM:
                if j + 1 < len(tu) and tu[j + 1] == "for" and "gift" not in c and "gifts" not in c:
                    hong = True  # "nurse shirt for women" bỏ chữ áo thành "nurse for women" -> sai nghĩa
                continue
            giu.append(w)
        if hong or len(giu) < 2 or giu[-1] in ("for", "and", "a", "the", "of"):
            continue
        if any(w not in cho for w in giu):
            continue
        if any(w in ("men", "women") and (j == 0 or giu[j - 1] != "for") for j, w in enumerate(giu)):
            continue
        giu = ["gifts" if w == "gift" else w for w in giu]
        cum = " ".join(giu)
        if any(_co_tu(cum, t) for t in TU_CAM):
            continue
        tok = _token(giu)
        if nu is not None and set(tok) & (NAM if nu else NU):
            continue
        if tk_set is not None and any(t in TU_DUOC or t.startswith("for ") for t in tok
                                      if t not in set(ng) | duoi_nghe | {"gifts"}) and \
                not all(t in tk_set for t in tok if (t in TU_DUOC or t.startswith("for ")) and
                        t not in set(ng) | duoi_nghe | {"gifts"}):
            continue
        khoa = frozenset(giu)
        if khoa in da or len(set(giu) - set(ng) - duoi_nghe) == 0:
            continue
        da.add(khoa)
        if giu[0] in DIP_LE:
            loai = "dip"  # "christmas nurse" -> "Christmas nurse outfits"
        elif "gifts" in giu:
            loai = "qua"
        elif giu[-1] in duoi_nghe | {"dad", "mom", "wife", "husband", "grandpa", "crew", "squad", "team"}:
            loai = "nguoi"
        else:
            continue  # "welder funny", "nurse humor"... đặt vào câu nghe gượng -> bỏ
        hoa = {w.lower(): w for w in nganh.split() if w.isupper() or w.lower() in MAU_GIU_HOA}
        hoa.update({w + "s": hoa[w] + "s" for w in list(hoa)})
        cum = " ".join(w.capitalize() if w in DIP_LE else hoa.get(w, w) for w in cum.split())
        cum = re.sub(r"\b(veterans|fathers|mothers|valentines|memorial|independence|labor) day\b",
                     lambda m: m.group(1).capitalize() + " Day", cum)
        ra.append((cum, loai))
        if len(ra) >= toi_da:
            break
    return ra


def _chon(chu, n):
    """Chọn biến thể câu ổn định theo chữ design -> mỗi design một kiểu câu, chạy lại vẫn y nguyên."""
    import zlib
    return zlib.crc32((chu or "").lower().encode("utf-8")) % n


def link_uspto(chu):
    """Trang tra nhãn hiệu Mỹ cho câu chữ design (tự động gọi bị tường lửa AWS chặn -> mở trên trình duyệt)."""
    return "https://tmsearch.uspto.gov/search/search-results?query=" + urllib.parse.quote(chu or "") + \
        "&section=default"


# ---------------- ghép ----------------
def _co_tu(chuoi, w):
    return re.search(r"(?<![a-z])" + re.escape(w.lower()) + r"(?![a-z])", chuoi.lower()) is not None


# Từ mùa vụ / dịp: title Merch giữ quanh năm -> chỉ vào title khi chính design nói về mùa/dịp đó
# (từ -> gốc chữ tìm trong design). Không vào title thì vẫn nằm ở bullet/description cho Amazon đọc.
TU_MUA = {"christmas": ("christmas", "xmas", "santa", "merry"), "halloween": ("halloween", "spooky", "boo"),
          "thanksgiving": ("thanksgiving", "turkey"), "valentines": ("valentine",), "easter": ("easter",),
          "fathers": ("father",), "mothers": ("mother",), "day": ("day",), "graduation": ("grad",)}
TU_DIP = {"retirement": ("retire",), "retired": ("retire",), "birthday": ("birthday", "bday"),
          "appreciation": ("appreciat", "thank"), "week": ("week",)}
# Nhóm giọng điệu: title chỉ giữ 1 từ (xếp hạng cao nhất) -> không ra "Funny Proud Welder"
NHOM_HAI = {"funny", "humor", "humorous", "sarcastic", "joke", "pun", "novelty", "proud", "cute", "awesome",
            "cool", "badass", "patriotic", "gag"}


def la_mua_dip(w):
    return w in TU_MUA or w in TU_DIP


# Người nhận cụ thể: đưa vào title làm hẹp khách (Dad loại người mua cho mẹ) -> chỉ dùng khi chữ design có từ đó
NGUOI_NHAN = {"dad", "mom", "husband", "wife", "grandpa", "grandma", "papa", "nana", "father", "mother"}


# Người nhận trong chữ design -> ô tick thêm "for wife"... (Amazon nghề hẹp không gợi ý nhưng khách gõ "gifts for wife")
NGUOI_O_TICK = {"wife": "for wife", "husband": "for husband", "mom": "for mom", "mother": "for mom",
                "dad": "for dad", "father": "for dad", "grandpa": "for grandpa", "papa": "for grandpa",
                "grandma": "for grandma", "nana": "for grandma", "girlfriend": "for her", "boyfriend": "for him"}


def tk_theo_design(chu):
    """Ô tick người nhận lấy từ chữ design (thứ tự xuất hiện, không trùng)."""
    c = (chu or "").lower()
    ra = []
    for w, o in NGUOI_O_TICK.items():
        if _co_tu(c, w) and o not in ra:
            ra.append(o)
    return ra


def tk_cho_title(tk, chu, cho_mua=False):
    """Bỏ từ mùa/dịp (trừ khi design nói về nó hoặc cho_mua=True) + chỉ giữ 1 từ hài hước xếp hạng cao nhất."""
    c = (chu or "").lower()
    ra, co_hai = [], False
    for w in tk:
        if w in NGUOI_NHAN and not _co_tu(c, w):  # "Dad"/"Mom" chỉ vào title khi design nói về họ
            continue
        goc = TU_MUA.get(w) or TU_DIP.get(w)
        if goc and not cho_mua and not any(g in c for g in goc):
            continue
        if w in NHOM_HAI:
            if co_hai:
                continue
            co_hai = True
        ra.append(w)
    return ra


def tao_title(chu, nganh, tk, toi_da=TITLE_MAX, chu_max=40, cho_mua=False, gioi=None):
    """Chữ design (<=40 ký tự) + nghề (nếu chưa có) + từ khoá quanh năm theo hạng Amazon; 'Gifts For X' đặt cuối."""
    tk = tk_cho_title(tk, chu, cho_mua)
    chu = re.sub(r"\s+", " ", chu).strip()
    if nganh and (_co_tu(chu, nganh) or _co_tu(chu, so_nhieu(nganh))):
        # đã có nghề: câu vừa chỗ cho " Gifts" thì giữ trọn (không cắt cụt chữ cuối), dài hơn thì cắt ở 46
        chu_max = toi_da - 6 if len(chu) <= toi_da - 6 else max(chu_max, toi_da - len(" Gifts For Men"))
    if nganh and chu.lower() == nganh.lower():  # design chỉ ghi tên nghề -> "Proud Concrete Finisher", không "... Proud"
        chu = ""
    if len(chu) > chu_max:  # câu design dài: cắt ở ranh giới từ, chừa chỗ cho từ khoá
        chu = chu[:chu_max + 1].rsplit(" ", 1)[0].rstrip(",;-")
    co_nghe = not nganh or _co_tu(chu, nganh) or _co_tu(chu, so_nhieu(nganh))
    truoc, sau = [], []  # tính từ đứng trước nghề ("Funny Welder"), người/dịp đứng sau ("Welder Dad")

    def ghep(duoi=""):
        if co_nghe:
            phan = [chu] + truoc + sau
        else:
            phan = [chu] + truoc + [nganh] + sau
        return " ".join(p for p in phan if p) + duoi

    gioi = _boi_canh(nganh, tk, chu, gioi)[1]
    trai = NU if gioi == "nam" else (NAM if gioi == "nu" else set())  # design nói về vợ -> không "For Men"
    cho = next((w for w in tk if w.startswith("for ") and w not in trai), None)
    co_gifts = "gifts" in tk or cho is not None
    t0 = ghep()
    duoi = ""
    if co_gifts and not _co_tu(t0, "gifts") and not _co_tu(t0, "gift"):
        duoi = " Gifts" + (" " + chu_hoa(cho) if cho and not _co_tu(t0, cho) else "")
        if len(t0) + len(duoi) > toi_da:
            duoi = " Gifts" if len(t0) + 6 <= toi_da else ""
    nam = {"dad", "husband", "grandpa", "for men", "for him", "for dad", "for husband", "for grandpa"}
    nu = {"mom", "wife", "for women", "for her", "for mom", "for wife", "for grandma"}
    dung_sau = nam | nu | set(TU_MUA) | {"life", "crew", "squad", "team", "pride", "retirement", "appreciation",
                                         "birthday", "week"}
    nguoi = set()  # đã có người nhận nào (dad/mom...) -> không thêm người thứ hai / trái giới
    if cho:
        nguoi.add(cho)
    for w in tk:
        if w == "gifts" or w.startswith("for ") or _co_tu(ghep(), w) or _co_tu(duoi, w):
            continue
        if w in nam | nu:
            if any(n in nam | nu for n in nguoi if not n.startswith("for ")) or \
                    (w in nam and nguoi & nu) or (w in nu and nguoi & nam):
                continue
        ds = sau if w in dung_sau else truoc
        ds.append(chu_hoa(w))
        if len(ghep(duoi)) <= toi_da:
            if w in nam | nu:
                nguoi.add(w)
        else:
            ds.pop()
    return chu_hoa(ghep(duoi))


def tao_brand(nganh, tk):
    loai = "Funny" if TU_HAI & set(tk[:6]) else ("Patriotic" if "patriotic" in tk[:6] else "Proud")
    for b in (f"{loai} {nganh} Gifts Co", f"{nganh} Gifts Co", f"{nganh} Life", nganh):
        if len(b) <= BRAND_MAX:
            return b
    return nganh[:BRAND_MAX]


def _cat(s, n=BULLET_MAX):
    if len(s) <= n:
        return s
    s = s[:n].rsplit(" ", 1)[0].rstrip(",;")
    return s + "."


def _boi_canh(nganh, tk, chu="", gioi=None):
    """gioi: 'nam' / 'nu' theo chữ design (dad, wife...) hoặc khi anh chỉ để tick 1 giới; còn lại 'ca' (nhắc cả hai)."""
    hai_huoc = any(w in tk[:8] for w in ("funny", "humor", "sarcastic"))
    if gioi in ("nam", "nu", "ca"):  # đã biết (Claude nhìn ảnh / chữ OCR + tên file)
        return hai_huoc, gioi
    c = (chu or "").lower()
    co_nam = any(_co_tu(c, w) for w in ("dad", "husband", "grandpa", "papa", "father", "son", "man", "men", "him"))
    co_nu = any(_co_tu(c, w) for w in ("mom", "wife", "grandma", "nana", "mother", "daughter", "woman", "women",
                                       "her", "she", "girl", "lady"))
    if co_nam != co_nu:
        return hai_huoc, ("nam" if co_nam else "nu")
    if ("for women" in tk) != ("for men" in tk):
        return hai_huoc, ("nu" if "for women" in tk else "nam")
    return hai_huoc, "ca"


def tao_bullets(chu, nganh, tk, cum=None, gioi=None):
    """2 bullet. cum = cum_tu_khoa(...) -> rải cụm khách gõ thật (mỗi cụm dùng 1 lần), câu đổi theo design."""
    nhieu = so_nhieu(nganh)
    hai_huoc, gioi = _boi_canh(nganh, tk, chu, gioi)
    nu = gioi == "nu"
    nguoi = {"nu": "mom, wife, coworker or best friend", "nam": "dad, husband, coworker or best friend",
             "ca": "dad, mom, husband, wife or coworker"}[gioi]
    dip = [d for d in ("christmas", "birthday", "retirement", "appreciation") if d in tk[:20]]
    dip_txt = {"christmas": "Christmas", "birthday": "birthdays", "retirement": "retirement",
               "appreciation": "appreciation week"}
    dip_s = ", ".join(dip_txt[d] for d in dip[:3]) or "birthdays, Christmas and retirement"
    trich = f'"{chu}" ' if chu else ""
    qua = [c for c, l in (cum or []) if l == "qua"]
    ng = [c for c, l in (cum or []) if l == "nguoi"]
    khac = [c for c, l in (cum or []) if l == "dip"]
    v = _chon(chu, 3)
    yeu_nuoc = "patriotic" in tk
    vui = "funny" if hai_huoc else ("proud" if yeu_nuoc or "proud" in tk[:3] else "great")
    if qua:
        b1 = [f"{trich}design made for proud {nhieu}. A {vui} pick if you are shopping for {qua[0]} - "
              f"made for your {nguoi} on {dip_s}.",
              f"{trich}design for {nhieu} who love what they do. One of those {qua[0]} that "
              f"{'gets a real laugh' if hai_huoc else 'gets noticed'} - great for your {nguoi} on {dip_s}.",
              f"Give your {nguoi} this {trich}design on {dip_s}. It stands out among {qua[0]} "
              f"for anyone proud of the work they do."][v]
    else:
        b1 = (f"{trich}design made for proud {nhieu}. "
              f"{'A funny' if hai_huoc else 'A great'} {nganh} gift for your {nguoi} on {dip_s}, "
              f"or any day they deserve a little recognition for the work they do.")
    mo2 = ["Wear it at work, on your day off or at the next crew get-together.",
           "Wear it on shift, after hours or at the next family barbecue.",
           "Wear it to work, on weekends or anywhere you want to show what you do."][v]
    if ng:
        ai = ng[0] + (f" or {ng[1]}" if len(ng) > 1 else "")
        b2 = f"{mo2} Made for any {ai} {'with a sense of humor' if hai_huoc else 'who loves the job'}."
        if khac:
            b2 += f" Great for {khac[0]} outfits and everyday wear."
    else:
        b2 = (f"{mo2} {'Perfect for ' + nhieu + ' with a sense of humor' if hai_huoc else 'Perfect for ' + nhieu}"
              f" who love what they do and want everyone to know it.")
        if khac:
            b2 += f" Great for {khac[0]} outfits too."
    return _cat(b1), _cat(b2)


def tao_mo_ta(chu, nganh, tk, cum=None, gioi=None):
    """Product description (<=2000): 3 đoạn ngắn, KHÔNG nhắc loại sản phẩm (Merch cảnh báo 'product types').
    Dùng các cụm từ khoá chưa có trong bullet (qua[1:], nguoi[2:], dip[1:])."""
    nhieu = so_nhieu(nganh)
    hai_huoc, gioi = _boi_canh(nganh, tk, chu, gioi)
    nu = gioi == "nu"
    nguoi = {"nu": "mom, wife, sister, coworker or best friend", "nam": "dad, husband, brother, coworker or best friend",
             "ca": "dad, mom, husband, wife, coworker or best friend"}[gioi]
    dip = [d for d in ("christmas", "birthday", "retirement", "appreciation") if d in tk[:20]]
    dip_txt = {"christmas": "Christmas", "birthday": "a birthday", "retirement": "retirement",
               "appreciation": "appreciation week"}
    dip_s = ", ".join(dip_txt[d] for d in dip[:3]) or "a birthday, Christmas or retirement"
    qua = [c for c, l in (cum or []) if l == "qua"][1:3]
    ng = [c for c, l in (cum or []) if l == "nguoi"][2:4]
    khac = [c for c, l in (cum or []) if l == "dip"][1:3]
    mo = f'"{chu}" is a bold design' if chu else "A bold design"
    p1 = (f"{mo} made for {nhieu} who take pride in what they do. "
          + ("It brings the kind of humor only people in the trade really get." if hai_huoc else
             "It stands for hard work, pride and the people who keep this country running." if "patriotic" in tk
             else "It says it all without a single word from you."))
    if qua:
        p2 = (f"Looking for {' or '.join(qua)}? It makes a thoughtful pick for your {nguoi} - for {dip_s}, "
              f"a new job, or just to say thanks for the hard work.")
    else:
        p2 = (f"Looking for something special for the {nganh} in your life? It makes a thoughtful pick for your "
              f"{nguoi} - for {dip_s}, a new job, or just to say thanks for the hard work.")
    p3 = ("Wear it on the job, on your day off or at the next crew get-together "
          "and let everyone know what you do.")
    if ng:
        p3 = f"Whether you are a {' or a '.join(ng)}, wear it on the job, on your day off or anywhere in between."
    if khac:
        p3 += f" Also a fun pick for {' and '.join(khac)} outfits."
    return _cat(" ".join([p1, p2, p3]), MO_TA_MAX)


# Chữ chỉ loại sản phẩm: Merch tự gắn loại hàng, nhắc trong Title/Bullet/Description bị cảnh báo
TU_LOAI_HANG = ["t-shirt", "t-shirts", "tshirt", "tshirts", "shirt", "shirts", "tee", "tees", "hoodie", "hoodies",
                "sweatshirt", "sweatshirts", "tank top", "tank tops", "long sleeve", "v-neck", "raglan", "pullover",
                "zip hoodie", "popsocket", "popsockets", "phone case", "tote bag", "throw pillow", "mug"]


def soat(kq):
    """Danh sách cảnh báo: độ dài, từ cấm, chữ loại hàng ở mọi ô, ký tự lạ, lặp từ."""
    loi = []
    gioi_han = [("title", TITLE_MAX), ("brand", BRAND_MAX), ("bullet1", BULLET_MAX), ("bullet2", BULLET_MAX),
                ("description", MO_TA_MAX)]
    o_co = [o for o, _ in gioi_han if o in kq]
    for o, n in gioi_han:
        if o in kq and len(kq[o]) > n:
            loi.append(f"{o} {len(kq[o])}/{n} ký tự")
    tat = " ".join(kq[o] for o in o_co).lower()
    for nhom, ds in NHOM_CAM.items():
        for t in ds:
            if _co_tu(tat, t):
                loi.append(f"{nhom}: {t}")
    for t in TU_QUANG_CAO:
        if t in tat:
            loi.append(f"lời quảng cáo cấm: {t}")
    for o in o_co:
        co = [w for w in TU_LOAI_HANG if _co_tu(kq[o], w)]
        if co:
            loi.append(f"{o} nhắc loại hàng ({', '.join(co)}) — Amazon khuyên bỏ")
    if re.search(r"[^\x20-\x7E]", kq["title"]):
        loi.append("title có ký tự lạ/emoji")
    lap = [w for w in set(kq["title"].lower().split()) if kq["title"].lower().split().count(w) > 1
           and w not in TU_NOI]
    if lap:
        loi.append("title lặp từ: " + ", ".join(lap))
    return loi


def tao(chu, nganh, tk, brand=None, cau=None, cho_mua=False, giong=None, ocr="", gioi=None):
    """cau = câu gợi ý Amazon thô (goi_y_amazon) -> bullet/mô tả dùng cụm khách gõ thật; None = văn mẫu.
    giong = 'hai' / 'hao' / 'trung' (None = tự đoán từ chữ design)."""
    dau = []
    if giong is None:
        giong, dau = doan_giong(chu, ocr)
    tk = tk_theo_giong(tk, giong, chu + " " + (ocr or ""))
    if gioi not in ("nam", "nu", "ca"):  # giới khách: chữ chính trước, không rõ thì xem cả chữ OCR + tên file
        gioi = _boi_canh(nganh, tk, chu)[1]
        if gioi == "ca" and ocr:
            gioi = _boi_canh(nganh, tk, ocr)[1]
    kq = {"title": tao_title(chu, nganh, tk, cho_mua=cho_mua, gioi=gioi), "brand": brand or tao_brand(nganh, tk)}
    cum = None
    if cau:
        cum = cum_tu_khoa(nganh, cau, tk, None if gioi == "ca" else gioi == "nu")
        cum = [(c, l) for c, l in cum if c.lower() not in kq["title"].lower()]
    kq["bullet1"], kq["bullet2"] = tao_bullets(chu, nganh, tk, cum, gioi)
    kq["description"] = tao_mo_ta(chu, nganh, tk, cum, gioi)
    kq["gioi"] = gioi
    kq["uspto"] = link_uspto(chu)
    kq["giong"], kq["dau_giong"] = giong, dau
    kq["loi"] = soat(kq)
    return kq


def lam_anh(duong, nganh, tk, brand=None, cau=None):
    dong = doc_chu(duong, nganh)
    chu = chon_chu(dong, chu_tu_ten_file(duong), nganh)
    kq = tao(chu, nganh, tk, brand, cau, ocr=" ".join(d[0] for d in dong))
    kq.update(file=os.path.basename(duong), chu=chu, ocr=" | ".join(d[0] for d in dong),
              ten_file=" | ".join(chu_tu_ten_file(duong)))
    return kq


# Cột CSV: ban_quyen để trống = chưa soát; Claude (skill soat-ban-quyen) ghi 🔴/🟡/🟢 + lý do vào đây
COT_CSV = ["file", "chu", "giong", "title", "brand", "bullet1", "bullet2", "description", "loi", "rui_ro", "ban_quyen",
           "uspto", "ocr"]


def main():
    ap = argparse.ArgumentParser(description="Title/Brand/Bullet Amazon Merch từ ảnh design")
    ap.add_argument("duong", help="ảnh design hoặc thư mục")
    ap.add_argument("--nganh", help="tên nghề, vd Electrician (mặc định đoán từ tên thư mục)")
    ap.add_argument("--brand", help="brand cố định")
    ap.add_argument("--lam-moi", action="store_true", help="gọi lại Amazon, bỏ đệm")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        getattr(sys.stdout, "reconfigure")(encoding="utf-8")
    nganh = a.nganh or doan_nganh(a.duong)
    cau, nguon = goi_y_amazon(nganh, a.lam_moi)
    tk = tu_khoa(nganh, cau)
    print(f"Nghề: {nganh} | từ khoá ({nguon}): {', '.join(tk[:12])}")
    if os.path.isfile(a.duong):
        kq = lam_anh(a.duong, nganh, tk, a.brand, cau)
        for o in ("chu", "giong", "title", "brand", "bullet1", "bullet2", "description"):
            print(f"{o.upper():8} ({len(kq[o])}): {kq[o]}")
        print("Cảnh báo:", "; ".join(kq["loi"]) or "không")
        print("Tra nhãn hiệu USPTO:", kq["uspto"])
        return
    fs = sorted(f for f in os.listdir(a.duong) if f.lower().endswith(DUOI_ANH))
    ra = os.path.join(a.duong, "_MERCH.csv")
    cot = COT_CSV + ["ten_file"]
    tmp = ra + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cot)
        w.writeheader()
        for i, fn in enumerate(fs, 1):
            try:
                kq = lam_anh(os.path.join(a.duong, fn), nganh, tk, a.brand, cau)
            except Exception as e:
                kq = {"file": fn, "loi": [f"lỗi đọc ảnh: {e}"], "title": "", "brand": "", "bullet1": "",
                      "bullet2": "", "description": "", "chu": "", "ocr": "", "ten_file": ""}
            kq["loi"] = "; ".join(kq["loi"])
            w.writerow({k: kq.get(k, "") for k in cot})
            print(f"[{i}/{len(fs)}] {kq['title']}")
    os.replace(tmp, ra)
    print("Xong:", ra)


if __name__ == "__main__":
    main()
