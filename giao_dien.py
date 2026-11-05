"""Bo mau + kieu chung cho Etsy Design Tool (app.py, setup). Mau do tu trang Phuc An 04/11/2026:
nen anh bia #34477A, logo #364672, vang logo #D4B97B / #E2CD8E, do nhan #C6353C."""
import tkinter as tk
from tkinter import ttk

NAVY = "#34477A"
NAVY_DAM = "#24335C"
NAVY_NHAT = "#4A5E94"
VANG = "#D4B97B"
VANG_NHAT = "#E2CD8E"
DO = "#C6353C"
KEM = "#EEF1F7"  # nen chinh: xam xanh nhat (khong dung kem)
TRANG = "#FFFFFF"
CHU = "#1E2740"
CHU_PHU = "#6B7290"
TEN = "Etsy Design Tool"
PHIEN_BAN = "1.0"
FONT = "Segoe UI"
FONT_TD = "Bahnschrift"  # chu tieu de + so: net kieu chu in ao; may thieu thi tk tu thay
NAVY_TOI = "#1C2644"
VIEN = "#D8DDE8"
THE = "#FFFFFF"


def ap_kieu(goc):
    goc.configure(bg=KEM)
    s = ttk.Style(goc)
    s.theme_use("clam")
    s.configure(".", font=(FONT, 10), background=KEM, foreground=CHU)
    s.configure("TFrame", background=KEM)
    s.configure("TLabel", background=KEM, foreground=CHU)
    s.configure("Phu.TLabel", foreground=CHU_PHU, font=(FONT, 9))
    s.configure("TieuDe.TLabel", foreground=NAVY, font=(FONT_TD, 18, "bold"))
    s.configure("TCheckbutton", background=KEM, foreground=CHU)
    s.map("TCheckbutton", background=[("active", KEM)], indicatorcolor=[("selected", NAVY), ("!selected", TRANG)])
    s.configure("TLabelframe", background=KEM, bordercolor=VANG, relief="solid")
    s.configure("TLabelframe.Label", background=KEM, foreground=NAVY, font=(FONT, 10, "bold"))
    # nut chinh: vang tren navy chu
    s.configure("Chinh.TButton", background=VANG, foreground=NAVY_DAM, font=(FONT, 10, "bold"),
                borderwidth=0, padding=(18, 8), focuscolor=VANG)
    s.map("Chinh.TButton", background=[("disabled", "#E8E1CF"), ("active", VANG_NHAT)],
          foreground=[("disabled", "#A9A08A")])
    s.configure("TButton", background=TRANG, foreground=NAVY, bordercolor=NAVY_NHAT, borderwidth=1,
                padding=(12, 6), focuscolor=TRANG)
    s.map("TButton", background=[("active", "#EEF1F8"), ("disabled", KEM)], foreground=[("disabled", "#AAB")])
    s.configure("Horizontal.TProgressbar", troughcolor="#E6E2D6", background=VANG, bordercolor="#E6E2D6",
                lightcolor=VANG, darkcolor=VANG, thickness=14)
    s.configure("TEntry", fieldbackground=TRANG, bordercolor=NAVY_NHAT)
    s.configure("Vertical.TScrollbar", background="#E6E2D6", troughcolor=KEM, bordercolor=KEM, arrowcolor=NAVY)
    return s


def thanh_tren(cha, phu="", ten=None, chu_logo="ED"):
    """Dai navy tren cung: logo chu vang + dong phu."""
    f = tk.Frame(cha, bg=NAVY, height=64)
    f.pack(fill="x")
    f.pack_propagate(False)
    o = tk.Canvas(f, width=40, height=40, bg=NAVY, highlightthickness=0)
    o.pack(side="left", padx=(16, 10), pady=12)
    ve_logo(o, 40, chu_logo)
    tk.Label(f, text=(ten or TEN).upper(), bg=NAVY, fg=VANG, font=(FONT, 15, "bold")).pack(side="left")
    if phu:
        tk.Label(f, text=phu, bg=NAVY, fg=VANG_NHAT, font=(FONT, 9)).pack(side="left", padx=12, pady=(6, 0))
    tk.Frame(cha, bg=VANG, height=3).pack(fill="x")
    return f


def chup_cua_so(w, duong):
    """Chup noi dung cua so (ke ca khi bi che) bang PrintWindow - chi de kiem tra giao dien."""
    import ctypes
    from ctypes import wintypes
    from PIL import Image
    w.update()
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    hwnd = u.GetParent(w.winfo_id()) or w.winfo_id()
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    rong, cao = r.right - r.left, r.bottom - r.top
    hdc = u.GetWindowDC(hwnd)
    mdc = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, rong, cao)
    g.SelectObject(mdc, bmp)
    u.PrintWindow(hwnd, mdc, 2)
    buf = ctypes.create_string_buffer(rong * cao * 4)
    bi = (ctypes.c_uint32 * 10)(40, rong, (-cao) & 0xFFFFFFFF, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
    g.GetDIBits(mdc, bmp, 0, cao, buf, bi, 0)
    Image.frombuffer("RGBA", (rong, cao), buf, "raw", "BGRA", 0, 1).convert("RGB").save(duong)
    g.DeleteObject(bmp)
    g.DeleteDC(mdc)
    u.ReleaseDC(hwnd, hdc)


def ve_logo(c, n, chu="ED"):
    """Logo don gian: o tron vien vang, chu ED vang."""
    c.create_oval(2, 2, n - 2, n - 2, outline=VANG, width=2)
    c.create_text(n / 2, n / 2 + 1, text=chu, fill=VANG, font=(FONT, int(n * 0.32), "bold"))


# ---------------- widget ve tay (tk khong co nut bo goc) ----------------
def hinh_bo_goc(c, x1, y1, x2, y2, r, **kw):
    d = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
         x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return c.create_polygon(d, smooth=True, **kw)


KIEU_NUT = {
    "chinh": dict(nen=VANG, chu=NAVY_TOI, re=VANG_NHAT, vien=None),
    "phu": dict(nen=THE, chu=NAVY, re="#F3F5FA", vien=VIEN),
    "toi": dict(nen=NAVY_NHAT, chu="#FFFFFF", re="#5A6FA6", vien=None),
}


class Nut(tk.Canvas):
    """Nut bo goc. kieu: chinh (vang) | phu (trang vien) | toi (tren nen navy)."""

    def __init__(self, cha, chu, lenh, kieu="chinh", rong=None, cao=38, co=11, nen_cha=None):
        import tkinter.font as tkf
        self.f = tkf.Font(family=FONT_TD, size=co, weight="bold" if kieu == "chinh" else "normal")
        rong = rong or self.f.measure(chu) + 36
        super().__init__(cha, width=rong, height=cao, highlightthickness=0, bd=0,
                         bg=nen_cha or cha.cget("bg"), cursor="hand2")
        self.k, self.chu, self.lenh, self.on, self.re = KIEU_NUT[kieu], chu, lenh, True, False
        self.bind("<Enter>", lambda e: self._dat(re=True))
        self.bind("<Leave>", lambda e: self._dat(re=False))
        self.bind("<ButtonRelease-1>", lambda e: self.on and self.lenh and self.lenh())
        self.bind("<Configure>", lambda e: self._ve())
        self._ve()

    def _dat(self, re):
        self.re = re
        self._ve()

    def bat(self, on=True):
        self.on = on
        self.configure(cursor="hand2" if on else "arrow")
        self._ve()

    def doi_chu(self, chu):
        self.chu = chu
        self._ve()

    def _ve(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            w, h = int(self.cget("width")), int(self.cget("height"))
        k = self.k
        nen = k["nen"] if self.on else ("#5B6A93" if k is KIEU_NUT["toi"] else "#E3E6EE")
        if self.on and self.re:
            nen = k["re"]
        chu = k["chu"] if self.on else "#9AA3BC"
        hinh_bo_goc(self, 1, 1, w - 1, h - 1, min(10, h // 2), fill=nen, outline=k["vien"] or nen)
        self.create_text(w / 2, h / 2, text=self.chu, fill=chu, font=self.f)


class CongTac(tk.Frame):
    """Cong tac bat/tat + chu, gan voi BooleanVar."""

    def __init__(self, cha, chu, bien, nen=NAVY, mau_chu="#FFFFFF", phu=None):
        super().__init__(cha, bg=nen)
        self.bien = bien
        self.c = tk.Canvas(self, width=38, height=22, bg=nen, highlightthickness=0, cursor="hand2")
        self.c.pack(side="left", anchor="n", pady=2)
        o = tk.Frame(self, bg=nen)
        o.pack(side="left", padx=(10, 0), fill="x")
        l = tk.Label(o, text=chu, bg=nen, fg=mau_chu, font=(FONT, 10), anchor="w", cursor="hand2")
        l.pack(anchor="w")
        if phu:
            tk.Label(o, text=phu, bg=nen, fg="#AEB8D6", font=(FONT, 8), anchor="w", justify="left",
                     wraplength=200).pack(anchor="w")
        for w in (self.c, l):
            w.bind("<Button-1>", lambda e: self.bien.set(not self.bien.get()))
        bien.trace_add("write", lambda *a: self._ve())
        self._ve()

    def _ve(self):
        c = self.c
        c.delete("all")
        bat = self.bien.get()
        hinh_bo_goc(c, 1, 2, 37, 20, 9, fill=VANG if bat else "#56689A", outline=VANG if bat else "#56689A")
        x = 27 if bat else 11
        c.create_oval(x - 7, 4, x + 7, 18, fill=NAVY_TOI if bat else "#C9D1E6", outline="")


class ThanhTienDo(tk.Canvas):
    def __init__(self, cha, cao=8):
        super().__init__(cha, height=cao, highlightthickness=0, bd=0, bg=cha.cget("bg"))
        self.gt, self.loi = 0.0, False
        self.bind("<Configure>", lambda e: self._ve())

    def dat(self, gt, loi=False):
        self.gt, self.loi = max(0.0, min(1.0, gt)), loi
        self._ve()

    def _ve(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        hinh_bo_goc(self, 0, 0, w, h, h // 2, fill=VIEN, outline=VIEN)
        if self.gt > 0:
            x = max(h, w * self.gt)
            m = DO if self.loi else VANG
            hinh_bo_goc(self, 0, 0, x, h, h // 2, fill=m, outline=m)


def o_co(rong, cao, sang=False, o=12):
    """Nen o co (trong suot) de dat design len xem."""
    from PIL import Image, ImageDraw
    a, b = (("#E9ECF3", "#DADFEA") if sang else ("#2A3558", "#232D4D"))
    im = Image.new("RGB", (rong, cao), a)
    d = ImageDraw.Draw(im)
    for y in range(0, cao, o):
        for x in range((y // o) % 2 * o, rong, 2 * o):
            d.rectangle((x, y, x + o - 1, y + o - 1), fill=b)
    return im.convert("RGBA")
