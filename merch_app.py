"""Cửa sổ Merch Title: mở ảnh design -> đọc chữ -> Title / Brand / 2 Bullet cho Amazon Merch on Demand.
Mở: pythonw merch_app.py [ảnh hoặc thư mục ...]  (kéo thả vào "Merch Title.bat" cũng được)
Sửa ô "Chữ chính" hoặc bật/tắt từ khoá -> tiêu đề tự viết lại. Bấm "Chép" để dán vào Merch.
"""
import os as _os
import sys as _sys

if __name__ == "__main__":  # tự cập nhật trước khi nạp phần còn lại
    try:
        _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
        import tu_cap_nhat
        tu_cap_nhat.kiem_va_mo_lai("merch", _os.path.abspath(__file__))
    except ImportError:
        pass

import csv
import os
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk

import giao_dien as gd
import merch_tieu_de as mt

O_XEM = (330, 377)
O_RA = [("title", "Title", mt.TITLE_MAX, 2), ("brand", "Brand", mt.BRAND_MAX, 1),
        ("bullet1", "Bullet 1", mt.BULLET_MAX, 3), ("bullet2", "Bullet 2", mt.BULLET_MAX, 3),
        ("description", "Product description", mt.MO_TA_MAX, 5)]


class App(tk.Tk):
    def __init__(self, ban_dau):
        super().__init__()
        self.title("Merch Title")
        self.geometry("1180x880")
        self.minsize(1040, 720)
        gd.ap_kieu(self)
        ico = os.path.join(mt.GOC, "icon.ico")
        if os.path.exists(ico):
            try:
                self.iconbitmap(ico)
            except tk.TclError:
                pass
        self.ds, self.i = [], 0
        self.ocr = {}  # duong -> (dong OCR, goi y ten file)
        self.sua = {}  # duong -> chu chinh anh da sua
        self.tk_list, self.chon, self.cau = [], {}, []
        self.claude = {}  # duong -> kết quả Claude Opus nhìn ảnh (kiểu, chữ, giới, rủi ro)
        self.tu_dong = {}  # duong -> chữ chính tool tự điền (để biết anh có sửa tay không)
        self.tu_tat = set()
        self.tk_them = []  # ô tick người nhận theo chữ design: for wife, for husband...  # từ khoá tool tự bỏ tick vì không hợp kiểu design (funny ở design tự hào...)
        self.nganh_da_lay = None
        self.anh_tk = None
        self._hen = None
        self.v_nganh, self.v_brand, self.v_chu = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.v_mua = tk.BooleanVar(value=False)
        self.v_giong = tk.StringVar(value="Tự đoán")
        self.sua_giong = {}  # duong -> 'hai'/'hao'/'trung' anh chọn tay
        gd.thanh_tren(self, "Tiêu đề + từ khoá Amazon Merch", ten="Merch Title", chu_logo="MT")
        than = tk.Frame(self, bg=gd.KEM)
        than.pack(fill="both", expand=True)
        self._trai(than)
        self._phai(than)
        self.v_chu.trace_add("write", lambda *a: self._hen_tao())
        self.v_brand.trace_add("write", lambda *a: self._hen_tao())
        for p in ban_dau:
            self._them(p)
        if self.ds:
            self._mo(0)

    # ---------------- bên trái: ảnh ----------------
    def _trai(self, cha):
        b = tk.Frame(cha, bg=gd.KEM, width=370)
        b.pack(side="left", fill="y", padx=(18, 8), pady=16)
        b.pack_propagate(False)
        hang = tk.Frame(b, bg=gd.KEM)
        hang.pack(fill="x")
        gd.Nut(hang, "Chọn ảnh", self._chon_anh, "chinh", cao=34, co=10).pack(side="left")
        gd.Nut(hang, "Chọn thư mục", self._chon_tm, "phu", cao=34, co=10).pack(side="left", padx=8)
        self.c = tk.Canvas(b, width=O_XEM[0], height=O_XEM[1], bg=gd.TRANG, highlightthickness=1,
                           highlightbackground=gd.VIEN)
        self.c.pack(pady=(14, 6))
        self.l_ten = tk.Label(b, text="Chưa có ảnh", bg=gd.KEM, fg=gd.CHU_PHU, font=(gd.FONT, 9),
                              wraplength=340, justify="center")
        self.l_ten.pack()
        nav = tk.Frame(b, bg=gd.KEM)
        nav.pack(pady=8)
        gd.Nut(nav, "‹ Trước", lambda: self._mo(self.i - 1), "phu", cao=32, co=10).pack(side="left")
        self.l_dem = tk.Label(nav, text="0 / 0", bg=gd.KEM, fg=gd.NAVY, font=(gd.FONT_TD, 11), width=10)
        self.l_dem.pack(side="left")
        gd.Nut(nav, "Sau ›", lambda: self._mo(self.i + 1), "phu", cao=32, co=10).pack(side="left")
        self.nut_claude = gd.Nut(b, "✦ Claude Opus đọc design", self._doc_claude, "chinh", rong=330, cao=38, co=10)
        self.nut_claude.pack(pady=(4, 2))
        self.l_claude = tk.Label(b, text="Đọc đúng kiểu design + chữ chính + rủi ro thương hiệu cả thư mục\n"
                                         "(gói Max, ~6 giây/ảnh, đọc rồi lưu lại không đọc lại)",
                                 bg=gd.KEM, fg=gd.CHU_PHU, font=(gd.FONT, 8), justify="center", wraplength=340)
        self.l_claude.pack()
        self.bind("<Prior>", lambda e: self._mo(self.i - 1))
        self.bind("<Next>", lambda e: self._mo(self.i + 1))
        day = tk.Frame(b, bg=gd.KEM)
        day.pack(side="bottom", fill="x")
        self.nut_csv = gd.Nut(day, "Xuất CSV cả thư mục", self._xuat_csv, "chinh", rong=330, cao=44, co=12)
        self.nut_csv.pack()
        self.l_csv = tk.Label(day, text="Ra <thư mục>\\_MERCH.csv — mở bằng Excel", bg=gd.KEM, fg=gd.CHU_PHU,
                              font=(gd.FONT, 8))
        self.l_csv.pack(pady=(6, 0))

    # ---------------- bên phải: chữ + kết quả ----------------
    def _phai(self, cha):
        p = tk.Frame(cha, bg=gd.KEM)
        p.pack(side="left", fill="both", expand=True, padx=(8, 18), pady=16)
        h1 = tk.Frame(p, bg=gd.KEM)
        h1.pack(fill="x")
        for chu, bien, rong in (("Nghề", self.v_nganh, 18), ("Brand cố định (bỏ trống = tự đặt)", self.v_brand, 30)):
            o = tk.Frame(h1, bg=gd.KEM)
            o.pack(side="left", padx=(0, 14))
            tk.Label(o, text=chu, bg=gd.KEM, fg=gd.NAVY, font=(gd.FONT, 9, "bold")).pack(anchor="w")
            tk.Entry(o, textvariable=bien, width=rong, font=(gd.FONT, 11), relief="solid", bd=1).pack(anchor="w")
        o = tk.Frame(h1, bg=gd.KEM)
        o.pack(side="left", pady=(14, 0))
        gd.Nut(o, "Lấy từ khoá Amazon", lambda: self._lay_tu_khoa(lam_moi=True), "phu", cao=30, co=9).pack()

        h2 = tk.Frame(p, bg=gd.KEM)
        h2.pack(fill="x", pady=(12, 0))
        tk.Label(h2, text="Chữ chính trên design (sửa cho đúng — tiêu đề viết theo ô này)", bg=gd.KEM,
                 fg=gd.NAVY, font=(gd.FONT, 9, "bold")).pack(side="left", anchor="s")
        gd.Nut(h2, "Tra nhãn hiệu USPTO", self._tra_uspto, "phu", cao=26, co=9).pack(side="right")
        tk.Entry(p, textvariable=self.v_chu, font=(gd.FONT, 13), relief="solid", bd=1).pack(fill="x")
        self.k_goi_y = tk.Frame(p, bg=gd.KEM)
        self.k_goi_y.pack(fill="x", pady=(4, 0))
        h4 = tk.Frame(p, bg=gd.KEM)
        h4.pack(fill="x", pady=(6, 0))
        tk.Label(h4, text="Kiểu design", bg=gd.KEM, fg=gd.NAVY, font=(gd.FONT, 9, "bold")).pack(side="left")
        cb = ttk.Combobox(h4, textvariable=self.v_giong, state="readonly", width=20,
                          values=["Tự đoán"] + list(mt.GIONG_TEN.values()))
        cb.pack(side="left", padx=8)
        cb.bind("<<ComboboxSelected>>", lambda e: self._doi_giong())
        self.l_giong = tk.Label(h4, text="", bg=gd.KEM, fg=gd.CHU_PHU, font=(gd.FONT, 8))
        self.l_giong.pack(side="left")
        self.l_rui_ro = tk.Label(p, text="", bg=gd.KEM, fg=gd.DO, font=(gd.FONT, 9, "bold"), justify="left",
                                 wraplength=720)
        self.l_rui_ro.pack(anchor="w")

        tk.Label(p, text="Từ khoá — Amazon xếp hạng (khách gõ nhiều đứng trước), bỏ tick để không dùng",
                 bg=gd.KEM, fg=gd.NAVY, font=(gd.FONT, 9, "bold")).pack(anchor="w", pady=(10, 0))
        h3 = tk.Frame(p, bg=gd.KEM)
        h3.pack(fill="x")
        self.l_nguon = tk.Label(h3, text="", bg=gd.KEM, fg=gd.CHU_PHU, font=(gd.FONT, 8))
        self.l_nguon.pack(side="left")
        tk.Checkbutton(h3, text="Cho từ mùa/dịp vào Title (chỉ bật cho design mùa vụ)", variable=self.v_mua,
                       bg=gd.KEM, fg=gd.CHU_PHU, font=(gd.FONT, 8), activebackground=gd.KEM,
                       selectcolor=gd.TRANG, command=self._hen_tao).pack(side="right")
        tk.Label(p, text="(mùa)/(dịp)/(người) = chỉ dùng ở Bullet + Description, trừ khi chữ design có từ đó "
                         "— title bán quanh năm. Từ hài/tự hào tự tick theo Kiểu design. (design) = người nhận trong chữ design, "
                         "tick để title ra \"Gifts For Wife\"...", bg=gd.KEM, fg=gd.CHU_PHU, font=(gd.FONT, 8)).pack(anchor="w")
        self.k_tk = tk.Frame(p, bg=gd.KEM)
        self.k_tk.pack(fill="x")

        self.o_ra, self.l_so = {}, {}
        for k, ten, toi_da, cao in O_RA:
            dau = tk.Frame(p, bg=gd.KEM)
            dau.pack(fill="x", pady=(10, 0))
            tk.Label(dau, text=ten, bg=gd.KEM, fg=gd.NAVY, font=(gd.FONT_TD, 11, "bold")).pack(side="left")
            self.l_so[k] = tk.Label(dau, text="", bg=gd.KEM, fg=gd.CHU_PHU, font=(gd.FONT, 9))
            self.l_so[k].pack(side="left", padx=8)
            gd.Nut(dau, "Chép", lambda k=k: self._chep(k), "phu", cao=24, co=9).pack(side="right")
            t = tk.Text(p, height=cao, wrap="word", font=(gd.FONT, 11), relief="solid", bd=1, padx=6, pady=4)
            t.pack(fill="x")
            t.bind("<KeyRelease>", lambda e: self._dem())
            self.o_ra[k] = t
        self.l_loi = tk.Label(p, text="", bg=gd.KEM, fg=gd.DO, font=(gd.FONT, 9, "bold"), justify="left",
                              wraplength=720)
        self.l_loi.pack(anchor="w", pady=(8, 0))
        tk.Label(p, text="Nhắc: bấm \"Tra nhãn hiệu USPTO\" cho câu chữ design (LIVE ở nhóm quần áo = không dùng). "
                         "Xuất CSV rồi nhờ Claude \"soát bản quyền _MERCH.csv\" trước khi đăng.",
                 bg=gd.KEM, fg=gd.CHU_PHU, font=(gd.FONT, 8)).pack(anchor="w")

    # ---------------- tệp ----------------
    def _them(self, p):
        p = os.path.abspath(p)
        if os.path.isdir(p):
            self.ds += [os.path.join(p, f) for f in sorted(os.listdir(p)) if f.lower().endswith(mt.DUOI_ANH)]
        elif p.lower().endswith(mt.DUOI_ANH):
            self.ds.append(p)

    def _chon_anh(self):
        fs = filedialog.askopenfilenames(title="Chọn ảnh design", filetypes=[("Ảnh", "*.png *.jpg *.jpeg *.webp")])
        if fs:
            n = len(self.ds)
            for f in fs:
                self._them(f)
            self._mo(n)

    def _chon_tm(self):
        d = filedialog.askdirectory(title="Chọn thư mục design")
        if d:
            n = len(self.ds)
            self._them(d)
            if len(self.ds) > n:
                self._mo(n)

    def _mo(self, i):
        if not self.ds:
            return
        self._luu_sua()
        self.i = max(0, min(i, len(self.ds) - 1))
        d = self.ds[self.i]
        self.l_dem.config(text=f"{self.i + 1} / {len(self.ds)}")
        self.l_ten.config(text=os.path.basename(d))
        self._ve_anh(d)
        if d not in self.claude:
            r = mt.nap_claude(d)
            if r:
                self.claude[d] = r
        nganh = mt.doan_nganh(d)
        if nganh and (not self.v_nganh.get() or self.nganh_da_lay != nganh):
            self.v_nganh.set(nganh)
        if self.nganh_da_lay != self.v_nganh.get().strip():
            self._lay_tu_khoa()
        if d in self.ocr:
            self._sau_ocr(d)
        else:
            self.v_chu.set("(đang đọc chữ...)")
            threading.Thread(target=self._chay_ocr, args=(d,), daemon=True).start()

    def _ve_anh(self, d):
        try:
            im = Image.open(d).convert("RGBA")
            im.thumbnail(O_XEM, Image.LANCZOS)
            nen = gd.o_co(O_XEM[0], O_XEM[1], False, 12)
            nen.alpha_composite(im, ((O_XEM[0] - im.width) // 2, (O_XEM[1] - im.height) // 2))
            self.anh_tk = ImageTk.PhotoImage(nen)
            self.c.delete("all")
            self.c.create_image(0, 0, image=self.anh_tk, anchor="nw")
        except Exception as e:
            self.c.delete("all")
            self.c.create_text(O_XEM[0] / 2, O_XEM[1] / 2, text=f"Không mở được ảnh\n{e}", fill=gd.DO)

    def _chay_ocr(self, d):
        try:
            dong = mt.doc_chu(d, self.v_nganh.get().strip())
        except Exception as e:
            dong = []
            self.after(0, lambda: self.l_loi.config(text=f"Lỗi đọc chữ: {e}"))
        self.ocr[d] = (dong, mt.chu_tu_ten_file(d))
        self.after(0, lambda: self._sau_ocr(d) if self.ds and self.ds[self.i] == d else None)

    def _sau_ocr(self, d):
        dong, ten = self.ocr[d]
        nganh = self.v_nganh.get().strip()
        g = self.sua_giong.get(d)
        self.v_giong.set(mt.GIONG_TEN[g] if g else "Tự đoán")
        tu_dong = mt.chu_claude(self.claude[d]) if d in self.claude else mt.chon_chu(dong, ten, nganh)
        self.tu_dong[d] = tu_dong
        self.v_chu.set(self.sua.get(d) or tu_dong)
        for w in self.k_goi_y.winfo_children():
            w.destroy()
        tk.Label(self.k_goi_y, text="Bấm để thêm:", bg=gd.KEM, fg=gd.CHU_PHU, font=(gd.FONT, 8)).pack(side="left")
        goi_y = [mt.chu_hoa(d[0]) for d in dong] + [mt.chu_hoa(t) for t in ten]
        dai = 0
        for g in dict.fromkeys(goi_y):
            if dai > 95:
                break
            dai += len(g) + 3
            l = tk.Label(self.k_goi_y, text=g, bg=gd.TRANG, fg=gd.NAVY, font=(gd.FONT, 9), padx=6, pady=1,
                         relief="solid", bd=1, cursor="hand2")
            l.pack(side="left", padx=2)
            l.bind("<Button-1>", lambda e, g=g: self._noi_chu(g))

    def _doi_giong(self):
        if self.ds:
            ten = self.v_giong.get()
            g = next((k for k, v in mt.GIONG_TEN.items() if v == ten), None)
            if g:
                self.sua_giong[self.ds[self.i]] = g
            else:
                self.sua_giong.pop(self.ds[self.i], None)
        self._tao()

    def _ocr_hien(self):
        d = self.ds[self.i] if self.ds else None
        if not d:
            return ""
        dong, ten = self.ocr.get(d, ([], []))
        return " ".join([x[0] for x in dong] + list(ten))

    def _noi_chu(self, g):
        cu = self.v_chu.get().strip()
        self.v_chu.set((cu + " " + g).strip() if cu and not cu.startswith("(") else g)

    def _luu_sua(self):
        if self.ds and 0 <= self.i < len(self.ds):
            c = self.v_chu.get().strip()
            d = self.ds[self.i]
            if c and not c.startswith("(") and c != self.tu_dong.get(d):  # chỉ nhớ khi anh sửa tay
                self.sua[d] = c

    # ---------------- từ khoá ----------------
    def _lay_tu_khoa(self, lam_moi=False):
        nganh = self.v_nganh.get().strip()
        if not nganh:
            return
        self.nganh_da_lay = nganh
        self.l_nguon.config(text="Đang hỏi ô gợi ý Amazon...")

        def chay():
            cau, nguon = mt.goi_y_amazon(nganh, lam_moi)
            tk_ = mt.tu_khoa(nganh, cau)
            self.after(0, lambda: (setattr(self, "cau", cau), self._ve_tu_khoa(tk_, nguon, len(cau))))
        threading.Thread(target=chay, daemon=True).start()

    def _ve_tu_khoa(self, tk_, nguon, n):
        self.tk_list = tk_[:18]
        self.l_nguon.config(text=f"Nguồn: {nguon} — {n} câu khách gõ")
        self._ve_luoi()
        self._tao()

    def _ve_luoi(self):
        """Ô tick = người nhận lấy từ chữ design ("for wife"... mặc định chưa tick) + từ khoá Amazon."""
        for w in self.k_tk.winfo_children():
            w.destroy()
        cu = self.chon
        self.chon = {}
        luoi = [w for w in self.tk_them if w not in self.tk_list] + self.tk_list
        for j, w in enumerate(luoi):
            v = tk.BooleanVar(value=cu[w].get() if w in cu else w not in self.tk_them)
            v.trace_add("write", lambda *a: self._hen_tao())
            self.chon[w] = v
            nhan = f"{j + 1}. {w}" + (" (mùa)" if w in mt.TU_MUA else " (dịp)" if w in mt.TU_DIP
                                      else " (người)" if w in mt.NGUOI_NHAN else " (design)" if w in self.tk_them
                                      else "")
            tk.Checkbutton(self.k_tk, text=nhan, variable=v, bg=gd.KEM, fg=gd.CHU, font=(gd.FONT, 9),
                           activebackground=gd.KEM, selectcolor=gd.TRANG, anchor="w", width=17).grid(
                row=j // 5, column=j % 5, sticky="w")

    # ---------------- ghép ----------------
    def _hen_tao(self):
        if self._hen:
            self.after_cancel(self._hen)
        self._hen = self.after(250, self._tao)

    def _tk_chon(self):
        luoi = [w for w in self.tk_them if w not in self.tk_list] + self.tk_list
        return [w for w in luoi if self.chon.get(w) is not None and self.chon[w].get()]

    def _tao(self):
        self._hen = None
        chu = self.v_chu.get().strip()
        if chu.startswith("("):
            return
        d = self.ds[self.i] if self.ds else None
        cl = self.claude.get(d)
        them = mt.tk_theo_design(chu + " " + (cl or {}).get("chu", ""))
        if them != self.tk_them and self.tk_list:
            self.tk_them = them
            self._ve_luoi()
        kq = mt.tao(chu, self.v_nganh.get().strip(), self._tk_chon(), self.v_brand.get().strip() or None,
                    self.cau, self.v_mua.get(), self.sua_giong.get(d) or (cl or {}).get("giong"), self._ocr_hien(),
                    (cl or {}).get("gioi"))
        self._tick_theo_giong(kq["giong"], chu)
        rr = (cl or {}).get("rui_ro") or []
        self.l_rui_ro.config(text=("⚠ Claude thấy rủi ro: " + " · ".join(rr)) if rr else "")
        if d in self.sua_giong:
            self.l_giong.config(text="(anh chọn tay)")
        elif cl:
            self.l_giong.config(text=f"Claude Opus: {mt.GIONG_TEN[cl['giong']]} — {cl.get('ly_do', '')}"[:150])
        else:
            self.l_giong.config(text=f"Đoán: {mt.GIONG_TEN[kq['giong']]}"
                                     + (f" — dấu hiệu: {', '.join(kq['dau_giong'][:5])}" if kq["dau_giong"]
                                        else " — không thấy dấu hiệu hài/tự hào"))
        for k, *_ in O_RA:
            t = self.o_ra[k]
            t.delete("1.0", "end")
            t.insert("1.0", kq[k])
        self._dem()

    def _doc_claude(self):
        if not self.ds:
            messagebox.showinfo("Merch Title", "Chọn ảnh hoặc thư mục design trước.")
            return
        ds, nganh = list(self.ds), self.v_nganh.get().strip()
        self.nut_claude.bat(False)

        def bao(t):
            self.after(0, lambda: self.l_claude.config(text=t, fg=gd.NAVY))

        def chay():
            try:
                kq = mt.doc_claude(ds, nganh, bao=bao)
                self.claude.update(kq)
                tin, mau = f"Claude Opus đã đọc {len(kq)} / {len(ds)} design. Kiểu + chữ chính đã cập nhật.", "#2E7D4F"
            except Exception as e:
                tin, mau = f"Lỗi Claude: {e}", gd.DO

            def xong():
                self.l_claude.config(text=tin, fg=mau)
                self.nut_claude.bat(True)
                d = self.ds[self.i] if self.ds else None
                if d in self.ocr:
                    self._sau_ocr(d)
                    self._tao()
            self.after(0, xong)
        threading.Thread(target=chay, daemon=True).start()

    def _tick_theo_giong(self, giong, chu):
        """Ô tick phản ánh đúng từ được dùng: design tự hào -> bỏ tick funny/humor..., design hài -> bỏ tick proud.
        Từ tool tự bỏ sẽ tự tick lại khi sang design kiểu khác. Đổi bằng ô 'Kiểu design'."""
        giu = set(mt.tk_theo_giong(self.tk_list, giong, chu))
        bo = {w for w in self.tk_list if w not in giu}
        for w in self.tk_list:
            v = self.chon.get(w)
            if v is None:
                continue
            if w in bo and v.get():
                self.tu_tat.add(w)
                v.set(False)
            elif w not in bo and w in self.tu_tat:
                self.tu_tat.discard(w)
                v.set(True)

    def _lay(self, k):
        return self.o_ra[k].get("1.0", "end").strip()

    def _dem(self):
        kq = {k: self._lay(k) for k, *_ in O_RA}
        for k, _, toi_da, _ in O_RA:
            n = len(kq[k])
            self.l_so[k].config(text=f"{n} / {toi_da}", fg=gd.DO if n > toi_da else gd.CHU_PHU)
        loi = mt.soat(kq)
        self.l_loi.config(text=("⚠ " + " · ".join(loi)) if loi else "✓ Đạt giới hạn Merch, không thấy từ cấm",
                          fg=gd.DO if loi else "#2E7D4F")

    def _tra_uspto(self):
        chu = self.v_chu.get().strip()
        if not chu or chu.startswith("("):
            messagebox.showinfo("Merch Title", "Chưa có chữ chính để tra.")
            return
        webbrowser.open(mt.link_uspto(chu))

    def _chep(self, k):
        self.clipboard_clear()
        self.clipboard_append(self._lay(k))
        self.l_so[k].config(text=self.l_so[k].cget("text") + "  — đã chép")

    # ---------------- CSV ----------------
    def _xuat_csv(self):
        if not self.ds:
            messagebox.showinfo("Merch Title", "Chọn thư mục design trước.")
            return
        self._luu_sua()
        ds, nganh = list(self.ds), self.v_nganh.get().strip()
        tk_, brand, cau, mua = self._tk_chon(), self.v_brand.get().strip() or None, list(self.cau), self.v_mua.get()
        giong_tay = dict(self.sua_giong)
        ra = os.path.join(os.path.dirname(ds[self.i]), "_MERCH.csv")
        self.nut_csv.bat(False)

        def chay():
            cot = mt.COT_CSV
            hang = []
            for j, d in enumerate(ds, 1):
                self.after(0, lambda j=j: self.l_csv.config(text=f"Đang làm {j} / {len(ds)}..."))
                try:
                    if d not in self.ocr:
                        self.ocr[d] = (mt.doc_chu(d, nganh), mt.chu_tu_ten_file(d))
                    dong, ten = self.ocr[d]
                    cl = self.claude.get(d) or mt.nap_claude(d) or {}
                    chu = self.sua.get(d) or (mt.chu_claude(cl) if cl else mt.chon_chu(dong, ten, nganh))
                    kq = mt.tao(chu, nganh, tk_, brand, cau, mua, giong_tay.get(d) or cl.get("giong"),
                                " ".join([x[0] for x in dong] + list(ten)), cl.get("gioi"))
                    kq["rui_ro"] = " · ".join(cl.get("rui_ro") or [])
                    kq["giong"] = mt.GIONG_TEN[kq["giong"]]
                    kq.update(file=os.path.basename(d), chu=chu, ocr=" | ".join(d[0] for d in dong))
                except Exception as e:
                    kq = {"file": os.path.basename(d), "loi": [f"lỗi: {e}"]}
                kq["loi"] = "; ".join(kq.get("loi", []))
                if d not in self.sua and not (self.claude.get(d) or mt.nap_claude(d)):
                    kq["loi"] = ("chữ OCR chưa soát (bấm Claude Opus đọc design); " + kq["loi"]).strip("; ")
                hang.append({c: kq.get(c, "") for c in cot})
            tmp = ra + ".tmp"
            try:
                with open(tmp, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.DictWriter(f, fieldnames=cot)
                    w.writeheader()
                    w.writerows(hang)
                os.replace(tmp, ra)
                tin = f"Xong {len(hang)} mẫu → {ra}"
            except OSError as e:
                tin = f"Không ghi được CSV (đang mở trong Excel?): {e}"
            self.after(0, lambda: (self.l_csv.config(text=tin), self.nut_csv.bat(True)))
        threading.Thread(target=chay, daemon=True).start()


if __name__ == "__main__":
    App(sys.argv[1:]).mainloop()
