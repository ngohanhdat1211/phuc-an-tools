"""Cua so Etsy Design Tool: chon thu muc mockup / anh ao -> chay tach_design.py.
Ban xem truoc: mockup dang lam | design vua tach (nen o co); luoi design da tach ben duoi.
Mo: pythonw app.py [thu muc hoac anh ...]  (keo tha vao loi tat Desktop cung duoc)
"""
import os as _os
import sys as _sys

if __name__ == "__main__":  # tự cập nhật trước khi nạp phần còn lại
    try:
        _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        import tu_cap_nhat
        tu_cap_nhat.kiem_va_mo_lai("etsy", _os.path.abspath(__file__))
    except ImportError:
        pass

import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog

from PIL import Image, ImageTk

import giao_dien as gd

GOC = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.join(GOC, "tach_design.py")
REDESIGN = os.path.join(GOC, "redesign.py")
DUOI_ANH = (".jpg", ".jpeg", ".png", ".webp")
O_XEM = (240, 262)  # khung anh tren ban xem truoc
O_LUOI = (118, 135)  # o design trong luoi ket qua


def python_exe():
    # pythonw khong co cua so den; tien trinh con dung python.exe canh no (an bang CREATE_NO_WINDOW)
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        p = exe[:-len("pythonw.exe")] + "python.exe"
        if os.path.exists(p):
            return p
    return exe


def dem_thu_muc(p):
    """(so mockup, so da tach trong Design Claude)."""
    anh = [f for f in os.listdir(p) if f.lower().endswith(DUOI_ANH)]
    ra = os.path.join(p, "Design Claude")
    xong = len([f for f in os.listdir(ra) if f.lower().endswith(".png")]) if os.path.isdir(ra) else 0
    return len(anh), xong


def anh_nho(duong, o, nen_co=None, sang=False):
    """Mo anh, thu nho vua o; neu nen_co: dat len nen o co. Tra PIL RGB."""
    im = Image.open(duong)
    im.draft("RGB", (o[0] * 2, o[1] * 2))
    im = im.convert("RGBA")
    im.thumbnail(o, Image.LANCZOS)
    if nen_co is None:
        return im
    nen = gd.o_co(im.width, im.height, sang, 10)
    nen.alpha_composite(im)
    return nen


class App(tk.Tk):
    def __init__(self, ban_dau):
        super().__init__()
        self.title(gd.TEN)
        self.geometry("1120x720")
        self.minsize(980, 640)
        self.configure(bg=gd.KEM)
        ico = os.path.join(GOC, "icon.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except tk.TclError:
                pass
        self.q = queue.Queue()
        self.ds = []  # duong dan da chon
        self.dang_chay = False
        self.ket_qua = []  # (thu muc ra, file xem lai)
        self.anh_luoi = []  # (duong png, PIL RGBA nho) - giu de doi nen
        self.tk_giu = []  # giu PhotoImage khoi bi xoa
        self.xem = {"mock": None, "design": None}
        self.nen_sang = tk.BooleanVar(value=False)
        self.lam_lai = tk.BooleanVar(value=False)
        self.giu_xam = tk.BooleanVar(value=False)
        self.giu_ti_le = tk.BooleanVar(value=False)
        self.nhat_ky = []
        self.cua_so_log = None
        self.dem_loi = 0
        self._ben_trai()
        self._ben_phai()
        self.nen_sang.trace_add("write", lambda *a: self._ve_lai_nen())
        for p in ban_dau:
            self._them(p)
        self.after(100, self._doc_hang)

    # ================= thanh ben trai =================
    def _ben_trai(self):
        b = tk.Frame(self, bg=gd.NAVY, width=300)
        b.pack(side="left", fill="y")
        b.pack_propagate(False)
        self.ben = b
        dau = tk.Frame(b, bg=gd.NAVY)
        dau.pack(fill="x", padx=24, pady=(26, 0))
        c = tk.Canvas(dau, width=46, height=46, bg=gd.NAVY, highlightthickness=0)
        c.pack(side="left")
        gd.ve_logo(c, 46)
        t = tk.Frame(dau, bg=gd.NAVY)
        t.pack(side="left", padx=12)
        tk.Label(t, text="Etsy Design Tool", bg=gd.NAVY, fg=gd.VANG, font=(gd.FONT_TD, 16, "bold")).pack(anchor="w")
        tk.Label(t, text="Tách design từ mockup áo", bg=gd.NAVY, fg="#AEB8D6",
                 font=(gd.FONT, 9)).pack(anchor="w")
        tk.Frame(b, bg="#4A5E94", height=1).pack(fill="x", padx=24, pady=22)

        tk.Label(b, text="Thư mục mockup", bg=gd.NAVY, fg=gd.VANG_NHAT, font=(gd.FONT_TD, 11)).pack(
            anchor="w", padx=24)
        self.khung_ds = tk.Frame(b, bg=gd.NAVY)
        self.khung_ds.pack(fill="x", padx=18, pady=(8, 6))
        hang = tk.Frame(b, bg=gd.NAVY)
        hang.pack(fill="x", padx=24, pady=(4, 0))
        gd.Nut(hang, "+  Thêm thư mục", self._chon_thu_muc, "toi", cao=34, co=10).pack(side="left")
        l = tk.Label(hang, text="hoặc ảnh lẻ", bg=gd.NAVY, fg="#AEB8D6", font=(gd.FONT, 9, "underline"),
                     cursor="hand2")
        l.pack(side="left", padx=12)
        l.bind("<Button-1>", lambda e: self._chon_anh())

        tk.Frame(b, bg="#4A5E94", height=1).pack(fill="x", padx=24, pady=22)
        tk.Label(b, text="Tuỳ chọn", bg=gd.NAVY, fg=gd.VANG_NHAT, font=(gd.FONT_TD, 11)).pack(anchor="w", padx=24)
        for chu, bien, phu in [
            ("Làm lại mẫu đã tách", self.lam_lai, "Ghi đè file đã có trong Design Claude"),
            ("Giữ phần đen", self.giu_xam, "Bật khi in lên áo màu sáng"),
            ("Giữ tỉ lệ design", self.giu_ti_le, "Tắt: kéo kín khung 4200 × 4800"),
        ]:
            gd.CongTac(b, chu, bien, phu=phu).pack(fill="x", padx=24, pady=(10, 0))

        day = tk.Frame(b, bg=gd.NAVY)
        day.pack(side="bottom", fill="x", padx=24, pady=24)
        self.nut_chay = gd.Nut(day, "Tách design", self._bat_dau, "chinh", rong=252, cao=48, co=13)
        self.nut_chay.pack(fill="x")
        self.nut_rd = gd.Nut(day, "✦  Redesign bằng Claude", self._redesign, "toi", rong=252, cao=36, co=10)
        self.nut_rd.pack(fill="x", pady=(10, 0))
        l = tk.Label(day, text="Xem nhật ký", bg=gd.NAVY, fg="#AEB8D6", font=(gd.FONT, 9, "underline"),
                     cursor="hand2")
        l.pack(pady=(10, 0))
        l.bind("<Button-1>", lambda e: self._mo_log())
        self._ve_ds()

    def _ve_ds(self):
        for w in self.khung_ds.winfo_children():
            w.destroy()
        if not self.ds:
            tk.Label(self.khung_ds, text="Chưa chọn thư mục nào.", bg=gd.NAVY, fg="#8D99BE",
                     font=(gd.FONT, 9)).pack(anchor="w", padx=6, pady=4)
        for p in self.ds[:6]:
            h = tk.Frame(self.khung_ds, bg="#3E5389")
            h.pack(fill="x", pady=3)
            o = tk.Frame(h, bg="#3E5389")
            o.pack(side="left", fill="x", expand=True, padx=12, pady=7)
            tk.Label(o, text=os.path.basename(p) or p, bg="#3E5389", fg="#FFFFFF", font=(gd.FONT, 10, "bold"),
                     anchor="w").pack(anchor="w")
            if os.path.isdir(p):
                n, xong = dem_thu_muc(p)
                phu = f"{n} mockup, {xong} đã tách"
            else:
                phu = "Ảnh lẻ"
            tk.Label(o, text=phu, bg="#3E5389", fg="#C9D1E6", font=(gd.FONT, 8), anchor="w").pack(anchor="w")
            x = tk.Label(h, text="✕", bg="#3E5389", fg="#C9D1E6", font=(gd.FONT, 10), cursor="hand2")
            x.pack(side="right", padx=10)
            x.bind("<Button-1>", lambda e, p=p: self._bo(p))
        if len(self.ds) > 6:
            tk.Label(self.khung_ds, text=f"và {len(self.ds) - 6} mục nữa", bg=gd.NAVY, fg="#AEB8D6",
                     font=(gd.FONT, 9)).pack(anchor="w", padx=6)
        if hasattr(self, "san"):
            self._ve_san()

    # ================= phan chinh =================
    def _ben_phai(self):
        p = tk.Frame(self, bg=gd.KEM)
        p.pack(side="left", fill="both", expand=True, padx=28, pady=24)
        self.san = tk.Canvas(p, height=400, bg=gd.NAVY_TOI, highlightthickness=0)
        self.san.pack(fill="x")
        self.san.bind("<Configure>", lambda e: self._ve_san())
        self.san.bind("<Button-1>", self._bam_san)
        self.dang = {"ten": "", "i": 0, "n": 0}

        self.thanh = gd.ThanhTienDo(p, 8)
        self.thanh.pack(fill="x", pady=(16, 8))
        h = tk.Frame(p, bg=gd.KEM)
        h.pack(fill="x")
        self.trang_thai = tk.Label(h, text="Chọn thư mục mockup ở bên trái rồi bấm Tách design.", bg=gd.KEM,
                                   fg=gd.NAVY, font=(gd.FONT, 10), anchor="w")
        self.trang_thai.pack(side="left")
        self.nut_xem = gd.Nut(h, "Mở tờ xem lại", self._mo_xem_lai, "phu", cao=34, co=10)
        self.nut_xem.pack(side="right")
        self.nut_mo = gd.Nut(h, "Mở thư mục kết quả", self._mo_ket_qua, "phu", cao=34, co=10)
        self.nut_mo.pack(side="right", padx=8)
        self.nut_xem.bat(False)
        self.nut_mo.bat(False)

        dau = tk.Frame(p, bg=gd.KEM)
        dau.pack(fill="x", pady=(22, 8))
        self.tieu_de_luoi = tk.Label(dau, text="Design đã tách", bg=gd.KEM, fg=gd.NAVY_TOI,
                                     font=(gd.FONT_TD, 13, "bold"))
        self.tieu_de_luoi.pack(side="left")
        gd.CongTac(dau, "Nền sáng", self.nen_sang, nen=gd.KEM, mau_chu=gd.NAVY).pack(side="right")
        k = tk.Frame(p, bg=gd.KEM)
        k.pack(fill="both", expand=True)
        self.luoi = tk.Canvas(k, bg=gd.KEM, highlightthickness=0)
        cuon = tk.Scrollbar(k, command=self.luoi.yview)
        self.luoi.configure(yscrollcommand=cuon.set)
        cuon.pack(side="right", fill="y")
        self.luoi.pack(side="left", fill="both", expand=True)
        self.luoi.bind("<Configure>", lambda e: self._ve_luoi())
        self.luoi.bind_all("<MouseWheel>", lambda e: self.luoi.yview_scroll(int(-e.delta / 120), "units"))

    def _ve_san(self):
        c = self.san
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if self.xem["mock"] is None and self.xem["design"] is None:
            gd.hinh_bo_goc(c, 28, 28, w - 28, h - 28, 14, fill="", outline="#3A4A78", dash=(6, 5), width=2)
            if self.ds:
                to, nho = "Sẵn sàng tách design", "Bấm Tách design ở góc dưới bên trái"
            else:
                to, nho = ("Chọn thư mục mockup để bắt đầu",
                           "Bấm vào đây, hoặc kéo thả thư mục vào biểu tượng ngoài Desktop")
            c.create_text(w / 2, h / 2 - 14, text=to, fill="#FFFFFF", font=(gd.FONT_TD, 16))
            c.create_text(w / 2, h / 2 + 16, text=nho, fill="#8D99BE", font=(gd.FONT, 10))
            return
        if self.dang["ten"]:
            c.create_text(28, 30, text=self.dang["ten"], fill="#FFFFFF", font=(gd.FONT, 11), anchor="w",
                          width=w - 180)
        if self.dang["n"]:
            c.create_text(w - 28, 30, text=f"{self.dang['i']} / {self.dang['n']}", fill=gd.VANG,
                          font=(gd.FONT_TD, 20, "bold"), anchor="e")
        cx1, cx2, cy = w * 0.28, w * 0.72, (58 + h - 36) / 2
        for cx, khoa, nhan in [(cx1, "mock", "Mockup"), (cx2, "design", "Design")]:
            anh = self.xem[khoa]
            if anh is not None:
                c.create_image(cx, cy, image=anh)
            else:
                c.create_text(cx, cy, text="đang tách…", fill="#8D99BE", font=(gd.FONT, 10))
            c.create_text(cx, h - 16, text=nhan, fill="#8D99BE", font=(gd.FONT, 9))
        # mui ten: mockup thanh design
        mx = w / 2
        c.create_line(mx - 26, cy, mx + 22, cy, fill=gd.VANG, width=2, arrow="last", arrowshape=(10, 12, 5))

    def _bam_san(self, e):
        if not self.dang_chay and self.xem["mock"] is None:
            self._chon_thu_muc()

    def _dat_xem(self, khoa, pil):
        if pil is None:
            self.xem[khoa] = None
        else:
            self.xem[khoa] = ImageTk.PhotoImage(pil)
        self._ve_san()

    def _ve_luoi(self):
        c = self.luoi
        c.delete("all")
        self.tk_giu = []
        w = max(c.winfo_width(), 200)
        ow, oh = O_LUOI[0] + 16, O_LUOI[1] + 16
        cot = max(1, (w + 12) // (ow + 12))
        if not self.anh_luoi:
            c.create_text(4, 8, anchor="nw", fill=gd.CHU_PHU, font=(gd.FONT, 10),
                          text="Design tách xong sẽ hiện ở đây. Bấm vào một design để mở file.")
            c.configure(scrollregion=(0, 0, w, 40))
            return
        for i, (duong, nho) in enumerate(self.anh_luoi):
            x, y = (i % cot) * (ow + 12), (i // cot) * (oh + 12)
            gd.hinh_bo_goc(c, x, y, x + ow, y + oh, 10, fill=gd.THE, outline=gd.VIEN)
            nen = gd.o_co(nho.width, nho.height, self.nen_sang.get(), 8)
            nen.alpha_composite(nho)
            ph = ImageTk.PhotoImage(nen)
            self.tk_giu.append(ph)
            the = c.create_image(x + ow / 2, y + oh / 2, image=ph)
            c.tag_bind(the, "<Button-1>", lambda e, d=duong: os.startfile(d))
            c.tag_bind(the, "<Enter>", lambda e: c.configure(cursor="hand2"))
            c.tag_bind(the, "<Leave>", lambda e: c.configure(cursor=""))
        dong = (len(self.anh_luoi) + cot - 1) // cot
        c.configure(scrollregion=(0, 0, w, dong * (oh + 12)))
        self.tieu_de_luoi.configure(text=f"Design đã tách  ({len(self.anh_luoi)})")

    def _ve_lai_nen(self):
        self._ve_luoi()
        if self.xem.get("design_pil") is not None:
            self._dat_xem("design", self._tren_nen(self.xem["design_pil"]))

    def _tren_nen(self, pil):
        nen = gd.o_co(pil.width, pil.height, self.nen_sang.get(), 12)
        nen.alpha_composite(pil)
        return nen

    # ================= danh sach =================
    def _them(self, p):
        p = os.path.normpath(p.strip('"'))
        if not os.path.exists(p) or (os.path.isfile(p) and not p.lower().endswith(DUOI_ANH)):
            return
        if p not in self.ds:
            self.ds.append(p)
        self._ve_ds()

    def _bo(self, p):
        if not self.dang_chay and p in self.ds:
            self.ds.remove(p)
            self._ve_ds()

    def _chon_thu_muc(self):
        p = filedialog.askdirectory(title="Chọn thư mục mockup")
        if p:
            self._them(p)

    def _chon_anh(self):
        for p in filedialog.askopenfilenames(title="Chọn ảnh áo", filetypes=[("Ảnh", "*.jpg *.jpeg *.png *.webp")]):
            self._them(p)

    # ================= nhat ky =================
    def _ghi(self, s):
        self.nhat_ky.append(s)
        if self.cua_so_log is not None and self.cua_so_log.winfo_exists():
            self.log.insert("end", s + "\n")
            self.log.see("end")

    def _mo_log(self):
        if self.cua_so_log is not None and self.cua_so_log.winfo_exists():
            self.cua_so_log.lift()
            return
        t = tk.Toplevel(self)
        t.title("Nhật ký — " + gd.TEN)
        t.geometry("820x420")
        t.configure(bg=gd.NAVY_TOI)
        self.log = tk.Text(t, bg=gd.NAVY_TOI, fg="#DDE3F2", font=("Consolas", 9), bd=0, padx=14, pady=10,
                           insertbackground=gd.VANG, wrap="word")
        self.log.pack(fill="both", expand=True)
        self.log.insert("end", "\n".join(self.nhat_ky) + ("\n" if self.nhat_ky else ""))
        self.log.see("end")
        self.cua_so_log = t

    # ================= chay =================
    def _bat_dau(self):
        if self.dang_chay:
            return
        if not self.ds:
            self._chon_thu_muc()
            if not self.ds:
                return
        self.dang_chay = True
        self.ket_qua, self.anh_luoi, self.dem_loi = [], [], 0
        self.xem = {"mock": None, "design": None}
        self.nut_chay.bat(False)
        self.nut_chay.doi_chu("Đang tách…")
        self.nut_mo.bat(False)
        self.nut_xem.bat(False)
        self.thanh.dat(0)
        self._ve_luoi()
        them = [c for c, b in [("--lam-lai", self.lam_lai), ("--giu-xam", self.giu_xam),
                               ("--giu-ti-le", self.giu_ti_le)] if b.get()]
        threading.Thread(target=self._chay_nen, args=(list(self.ds), them), daemon=True).start()

    def _chay_nen(self, ds, them):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        co = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        for k, p in enumerate(ds, 1):
            la_thu_muc = os.path.isdir(p)
            self.q.put(("log", f"===== [{k}/{len(ds)}] {p}"))
            if not la_thu_muc:
                self._bao_dang(p, 1, 1, k, len(ds))
            lenh = [python_exe(), "-u", TOOL, p] + them
            try:
                tt = subprocess.Popen(lenh, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
                                      creationflags=co, encoding="utf-8", errors="replace", cwd=GOC)
            except OSError as e:
                self.q.put(("loi", f"Không chạy được: {e}"))
                continue
            xem = None
            for dong in tt.stdout:
                dong = dong.rstrip()
                self.q.put(("log", dong))
                m = re.match(r"\[(\d+)/(\d+)\] (.+)$", dong)
                if m and la_thu_muc:
                    self._bao_dang(os.path.join(p, m.group(3)), int(m.group(1)), int(m.group(2)), k, len(ds))
                elif dong.startswith("Da luu:"):
                    ra = dong.split(":", 1)[1].strip()
                    try:
                        self.q.put(("design", (ra, anh_nho(ra, O_XEM), anh_nho(ra, O_LUOI))))
                    except OSError:
                        pass
                elif "LOI" in dong:
                    self.q.put(("loi", dong))
                elif dong.startswith("To xem lai:"):
                    xem = dong.split(":", 1)[1].strip()
            tt.wait()
            if tt.returncode != 0:
                self.q.put(("loi", f"Lỗi khi chạy {os.path.basename(p)} (mã {tt.returncode})"))
            ra = os.path.join(p, "Design Claude") if la_thu_muc else os.path.dirname(p)
            self.q.put(("ket", (ra, xem)))
        self.q.put(("xong", None))

    # ================= redesign =================
    def _redesign(self):
        """Chọn design đã tách -> Claude (gói Max trên máy) vẽ mẫu mới cùng ngách -> thư mục Redesign Claude."""
        if self.dang_chay:
            return
        goc = next((os.path.join(p, "Design Claude") for p in self.ds
                    if os.path.isdir(os.path.join(p, "Design Claude"))), None)
        ds = filedialog.askopenfilenames(title="Chọn design để redesign", initialdir=goc,
                                         filetypes=[("Ảnh", "*.png *.jpg *.jpeg *.webp")])
        if not ds:
            return
        so = simpledialog.askinteger("Redesign", "Mỗi design làm bao nhiêu mẫu mới? (1-5)\n"
                                     "Mỗi mẫu ~2 phút, dùng hạn mức gói Claude Max.", initialvalue=1,
                                     minvalue=1, maxvalue=5, parent=self)
        if not so:
            return
        self.dang_chay = True
        self.ket_qua, self.anh_luoi, self.dem_loi = [], [], 0
        self.nut_chay.bat(False)
        self.nut_rd.bat(False)
        self.nut_rd.doi_chu("Claude đang vẽ…")
        self.thanh.dat(0)
        self._ve_luoi()
        threading.Thread(target=self._chay_redesign, args=(list(ds), so), daemon=True).start()

    def _chay_redesign(self, ds, so):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        co = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        tong, xong = len(ds) * so, 0
        for k, p in enumerate(ds, 1):
            self.q.put(("log", f"===== Redesign [{k}/{len(ds)}] {p}"))
            self._bao_dang(p, xong + 1, tong, 1, 1)
            try:
                tt = subprocess.Popen([python_exe(), "-u", REDESIGN, p, "--so", str(so)], stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, env=env, creationflags=co, encoding="utf-8",
                                      errors="replace", cwd=GOC)
            except OSError as e:
                self.q.put(("loi", f"Không chạy được: {e}"))
                continue
            for dong in tt.stdout:
                dong = dong.rstrip()
                self.q.put(("log", dong))
                if dong.startswith("Da luu:"):
                    ra = dong.split(":", 1)[1].strip()
                    xong += 1
                    self.dang = {"ten": "", "i": xong, "n": tong}
                    try:
                        self.q.put(("design", (ra, anh_nho(ra, O_XEM), anh_nho(ra, O_LUOI))))
                    except OSError:
                        pass
                    self.q.put(("ket", (os.path.dirname(ra), None)))
                elif "LỖI" in dong or "Không thấy" in dong:
                    self.q.put(("loi", dong))
            tt.wait()
        self.q.put(("xong", None))

    def _bao_dang(self, mockup, i, n, k, tong):
        try:
            mock = anh_nho(mockup, O_XEM).convert("RGB")
        except OSError:
            mock = None
        nhan = os.path.splitext(os.path.basename(mockup))[0]
        if tong > 1:
            nhan = f"{nhan}   ·   mục {k}/{tong}"
        self.q.put(("dang", (nhan, i, n, mock)))

    def _doc_hang(self):
        try:
            while True:
                loai, v = self.q.get_nowait()
                if loai == "log":
                    self._ghi(v)
                elif loai == "dang":
                    nhan, i, n, mock = v
                    self.dang = {"ten": nhan, "i": i, "n": n}
                    self.xem["design_pil"] = None
                    self.xem["design"] = None
                    self._dat_xem("mock", mock)
                    self.thanh.dat((i - 1) / max(n, 1))
                    self.trang_thai.configure(text=f"Đang tách mẫu {i} trên {n}…", fg=gd.NAVY)
                elif loai == "design":
                    ra, lon, nho = v
                    self.xem["design_pil"] = lon
                    self._dat_xem("design", self._tren_nen(lon))
                    self.anh_luoi.append((ra, nho))
                    self._ve_luoi()
                    self.thanh.dat(self.dang["i"] / max(self.dang["n"], 1))
                elif loai == "loi":
                    self.dem_loi += 1
                    self._ghi(v)
                    self.trang_thai.configure(text=v[:110], fg=gd.DO)
                elif loai == "ket":
                    self.ket_qua.append(v)
                elif loai == "xong":
                    self._xong()
        except queue.Empty:
            pass
        self.after(100, self._doc_hang)

    def _xong(self):
        self.dang_chay = False
        self.nut_chay.bat(True)
        self.nut_chay.doi_chu("Tách design")
        self.nut_rd.bat(True)
        self.nut_rd.doi_chu("✦  Redesign bằng Claude")
        self.thanh.dat(1, loi=bool(self.dem_loi))
        self.nut_mo.bat(bool(self.ket_qua))
        self.nut_xem.bat(any(x for _, x in self.ket_qua))
        moi = len(self.anh_luoi)
        if self.dem_loi:
            msg = f"Xong {moi} design, {self.dem_loi} mẫu lỗi. Bấm Xem nhật ký để biết mẫu nào."
        elif moi:
            msg = f"Đã tách {moi} design. Soát tờ xem lại trước khi in."
        else:
            msg = "Không có mẫu mới: các mẫu đã tách hoặc đã có design. Bật Làm lại mẫu đã tách nếu cần."
        self.trang_thai.configure(text=msg, fg=gd.DO if self.dem_loi else gd.NAVY)
        self._ve_ds()

    def _mo_ket_qua(self):
        for ra, _ in self.ket_qua:
            if os.path.isdir(ra):
                os.startfile(ra)

    def _mo_xem_lai(self):
        for _, xem in self.ket_qua:
            if xem:
                xem = xem if os.path.isabs(xem) else os.path.join(GOC, xem)
                if os.path.exists(xem):
                    os.startfile(xem)


if __name__ == "__main__":
    App(sys.argv[1:]).mainloop()
