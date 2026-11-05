"""Tự cập nhật tool từ GitHub (repo công khai, chỉ chứa mã tool).
Mỗi lần mở app: đọc phien_ban.json trên repo, file nào khác mã băm thì tải về, kiểm mã băm, thay file,
rồi mở lại app. Mất mạng / lỗi -> bỏ qua, chạy bản đang có. Thư mục mã nguồn (có .git) thì không cập nhật.
Đẩy bản mới (máy làm tool): python tool\\day_ban_moi.py
"""
import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request

REPO = "ngohanhdat1211/phuc-an-tools"
GOC_URL = f"https://raw.githubusercontent.com/{REPO}/main/"
DAY = os.path.dirname(os.path.abspath(__file__))
NHAT_KY = os.path.join(DAY, "tu_cap_nhat.log")


def bam(duong):
    return hashlib.sha256(open(duong, "rb").read()).hexdigest()


def _tai(ten, cho=6):
    url = GOC_URL + urllib.parse.quote(ten) + f"?t={int(time.time())}"
    req = urllib.request.Request(url, headers={"User-Agent": "PhucAnTools-Updater/1.0", "Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=cho) as r:
        return r.read()


def _ghi(s):
    try:
        with open(NHAT_KY, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + s + "\n")
    except OSError:
        pass


def cap_nhat(sp):
    """Trả về danh sách file đã thay (rỗng = không có gì mới / lỗi)."""
    if os.path.isdir(os.path.join(os.path.dirname(DAY), ".git")) or os.path.isdir(os.path.join(DAY, ".git")):
        return []
    try:
        ds = json.loads(_tai("phien_ban.json"))[sp]["file"]
    except Exception as e:  # mất mạng, repo chưa có -> chạy bản cũ
        _ghi(f"không đọc được bản mới: {e}")
        return []
    thay = []
    for ten, ma in ds.items():
        dich = os.path.join(DAY, ten)
        if os.path.exists(dich) and bam(dich) == ma:
            continue
        try:
            du_lieu = _tai(ten, 30)
            if hashlib.sha256(du_lieu).hexdigest() != ma:
                _ghi(f"{ten}: mã băm không khớp, bỏ qua")
                continue
            tam = dich + ".moi"
            open(tam, "wb").write(du_lieu)
            os.replace(tam, dich)
            thay.append(ten)
        except Exception as e:
            _ghi(f"{ten}: lỗi tải {e}")
    if thay:
        _ghi("đã cập nhật: " + ", ".join(thay))
    return thay


def kiem_va_mo_lai(sp, file_app):
    """Gọi đầu chương trình. Có file mới -> mở lại app bằng mã mới rồi thoát bản đang chạy."""
    if os.environ.get("DA_CAP_NHAT"):
        return
    if cap_nhat(sp):
        subprocess.Popen([sys.executable, file_app, *sys.argv[1:]], env=dict(os.environ, DA_CAP_NHAT="1"))
        sys.exit(0)
