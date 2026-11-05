"""Tach design khoi anh ao (nen ao mau tron) -> PNG trong suot 4200x4800.

Vi du:
  python tool\tach_design.py anh\ao.jpg
  python tool\tach_design.py anh\ao.jpg --vung 330,440,920,1400 --nen "#1c2238"
  python tool\tach_design.py anh\ao.jpg --nguong 18,45

Cach lam: lay mau nen ao -> do khoang cach mau (Lab) -> do trong suot mem,
bo vien mau ao o mep (un-premultiply), giu khoi design lon nhat (bo ngon tay,
co ao), cat sat, phong to vua khung 4200x4800 can giua.
"""
import argparse
import os

import cv2
import numpy as np
from PIL import Image

W_OUT, H_OUT = 4200, 4800


def doc_mau(s):
    s = s.lstrip("#")
    return np.array([int(s[i:i + 2], 16) for i in (0, 2, 4)], np.uint8)  # RGB


def tim_mau_nen(rgb):
    """Mau ao = cum mau pho bien nhat o vung giua anh (ao chiem nhieu nhat)."""
    h, w = rgb.shape[:2]
    giua = rgb[int(h * .2):int(h * .8), int(w * .2):int(w * .8)]
    px = cv2.resize(giua, (120, 120), interpolation=cv2.INTER_AREA).reshape(-1, 3).astype(np.float32)
    _, nhan, tam = cv2.kmeans(px, 6, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1),
                              5, cv2.KMEANS_PP_CENTERS)
    dem = np.bincount(nhan.ravel(), minlength=6)
    return tam[dem.argmax()].round().astype(np.uint8)


def lab_cua(nen):
    """Lab cua 1 mau (3,) hoac ban do mau ao tung diem (h, w, 3)."""
    n = np.ascontiguousarray(nen.round().clip(0, 255).astype(np.uint8))
    return cv2.cvtColor(n.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).astype(np.float32).reshape(n.shape)


def khoang_cach(rgb, nen):
    lab = cv2.cvtColor(rgb.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).astype(np.float32).reshape(rgb.shape)
    lab_nen = lab_cua(nen)
    d = lab - lab_nen
    # Nep nhan tren ao doi do sang nhieu hon doi mau -> giam trong so L
    return np.sqrt((d[..., 0] * 0.6) ** 2 + d[..., 1] ** 2 + d[..., 2] ** 2)


def nguong_tu_dong(rgb, nen=None):
    """Do do loang cua vai ao (heather, nep nhan) -> mau ao + nguong t1,t2 hop voi tung anh."""
    h, w = rgb.shape[:2]
    px = rgb[int(h * .15):int(h * .85):2, int(w * .15):int(w * .85):2].reshape(-1, 3)
    px = px[np.random.default_rng(0).permutation(len(px))[:30000]]
    lab = cv2.cvtColor(px.reshape(-1, 1, 3), cv2.COLOR_RGB2LAB).reshape(-1, 3).astype(np.float32)
    lab[:, 0] *= 0.6
    # Mau ao = o mau pho bien nhat (khong ngau nhien -> chay lan nao cung ra mot ket qua)
    o = np.floor(lab / 4).astype(np.int32)
    ma = (o[:, 0] * 64 + (o[:, 1] % 64)) * 64 + (o[:, 2] % 64)
    gia_tri, dem = np.unique(ma, return_counts=True)
    dinh = lab[ma == gia_tri[dem.argmax()]].mean(axis=0)
    vai = px[np.linalg.norm(lab - dinh, axis=1) < 14]  # diem sat mau ao = van la vai
    if nen is None:
        nen = np.median(vai, axis=0).round().astype(np.uint8)
    kc = khoang_cach(vai.reshape(-1, 1, 3), nen).ravel()
    t1 = float(np.clip(np.percentile(kc, 99.5) + 2, 10, 45))
    return nen, t1, t1 + 22


def bo_suong(rgb, alpha, nen, mo=5):
    """Xoa 'suong': mang ban trong suot, mau xam trung tinh giong vai, rong thanh mang (khong phai mep net).
    Do la nep nhan / vet sang tren vai lot qua cac buoc truoc."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    lab_nen = lab_cua(nen)
    lech_mau = np.hypot(lab[..., 1] - lab_nen[..., 1], lab[..., 2] - lab_nen[..., 2])
    giua = ((alpha > 0.02) & (alpha < 0.8) & (lech_mau < 10)).astype(np.uint8)
    mang = cv2.morphologyEx(giua, cv2.MORPH_OPEN, np.ones((mo, mo), np.uint8))
    mang = cv2.dilate(mang, np.ones((3, 3), np.uint8)) & (alpha < 0.8)
    # Cho loang trong chu in (grunge) luon sat net dam; vet vai thi nam tach xa -> chi xoa phan xa net dam
    sat_net = cv2.dilate((alpha > 0.9).astype(np.uint8), np.ones((mo + 4, mo + 4), np.uint8))
    mang = mang & (sat_net == 0)
    alpha = alpha.copy()
    alpha[mang.astype(bool)] = 0
    return alpha


def nen_cuc_bo(rgb, nen, t1, t2, lan=2):
    """Anh nguoi mac / anh sang khong deu: mau ao doi dan theo vung (sang vai, toi nach).
    Lay mau vai that (diem gan mau ao), lam mo co trong so -> ban do mau ao tung diem; do lai nguong.
    Tra (ban do h x w x 3 float, t1, t2)."""
    h, w = rgb.shape[:2]
    f = rgb.astype(np.float32)
    s = max(h, w) * 0.03
    ban_do = np.broadcast_to(nen.astype(np.float32), f.shape)
    k = 4  # lam mo tren anh thu nho 1/4 roi phong lai (ban do mau ao rat muot, nhanh ~10 lan)
    nho = (max(1, w // k), max(1, h // k))

    def mo(x, sig):
        y = cv2.GaussianBlur(cv2.resize(x, nho, interpolation=cv2.INTER_AREA), (0, 0), sig / k)
        return cv2.resize(y, (w, h), interpolation=cv2.INTER_LINEAR)

    for _ in range(lan):
        vai = (do_trong_suot(rgb, ban_do, t1, t2) < 0.05).astype(np.uint8)
        vai = cv2.erode(vai, np.ones((5, 5), np.uint8)).astype(np.float32)
        fv = f * vai[..., None]
        so = mo(fv, s)
        mau = mo(vai, s)[..., None]
        so2 = mo(fv, s * 4)
        mau2 = mo(vai, s * 4)[..., None]
        xa = np.where(mau2 > 1e-3, so2 / np.maximum(mau2, 1e-6), nen.astype(np.float32))
        gan = so / np.maximum(mau, 1e-6)
        tin = np.clip(mau / 0.2, 0, 1)  # it vai quanh day (giua mang design lon) -> dung ban mo rong
        ban_do = gan * tin + xa * (1 - tin)
    kc = khoang_cach(rgb, ban_do)[vai > 0]
    if len(kc) > 1000:
        t1 = float(np.clip(np.percentile(kc, 99.5) + 2, 10, 45))
        t2 = t1 + 22
    return ban_do, t1, t2


def do_trong_suot(rgb, nen, t1, t2):
    kc = khoang_cach(rgb, nen)
    a = np.clip((kc - t1) / (t2 - t1), 0, 1)
    return a * a * (3 - 2 * a)  # smoothstep


def giu_khoi_design(alpha, vung, rgb, nen=None):
    h, w = alpha.shape
    if vung:
        x1, y1, x2, y2 = vung
        m = np.zeros_like(alpha)
        m[y1:y2, x1:x2] = 1
        return alpha * m
    # Design = phan "khong phai ao" bi ao bao kin (lo trong long ao).
    # Ngon tay, co, toc, tuong deu noi ra mep anh -> khong phai lo -> bi bo.
    ao = (alpha < 0.5).astype(np.uint8)
    n, nhan, tk, _ = cv2.connectedComponentsWithStats(ao)
    if n <= 1:
        return alpha
    ao = (nhan == 1 + tk[1:, 4].argmax()).astype(np.uint8)
    bien = np.zeros_like(ao)
    bien[0, :] = bien[-1, :] = 1
    bien[:, 0] = bien[:, -1] = 1
    # Cat cau noi manh (day mu, soi toc, ngon tay cham vao chu): mo hinh thai -> phan noi ra bien chi con
    # khoi day (tay, toc, tuong); chu dinh vao no qua cau manh duoc tach ra lam lo rieng.
    k = max(3, round(min(h, w) / 170)) | 1
    khong_ao = 1 - ao
    mo = cv2.morphologyEx(khong_ao, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    nm, nhan_mo = cv2.connectedComponents(mo)
    ra_bien = np.isin(nhan_mo, np.unique(nhan_mo[(bien == 1) & (mo == 1)])) & (mo == 1)
    ra_bien = cv2.dilate(ra_bien.astype(np.uint8), np.ones((3, 3), np.uint8)) & khong_ao
    con = khong_ao & (1 - ra_bien)
    n2, nhan2 = cv2.connectedComponents(con)
    nhan2[ra_bien == 1] = 0
    cham_bien = set(np.unique(nhan2[(bien == 1) & (con == 1)])) | {0}
    # Bo dom vai: manh nho (< 40px) va nhat (alpha cao nhat < 0.9) = soi xam cua vai heather, nep nhan
    dien_tich = np.bincount(nhan2.ravel(), minlength=n2)
    dam_nhat = np.zeros(n2, np.float32)
    np.maximum.at(dam_nhat, nhan2.ravel(), alpha.ravel())
    # Do sac mep: net in co mep sac, vet sang/nep nhan tren vai mep mo dan
    xam = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY).astype(np.float32)
    grad = np.hypot(cv2.Sobel(xam, cv2.CV_32F, 1, 0), cv2.Sobel(xam, cv2.CV_32F, 0, 1))
    nf = nhan2.astype(np.float32)
    vien = cv2.dilate(nf, np.ones((3, 3))) != cv2.erode(nf, np.ones((3, 3)))
    mep = np.bincount(nhan2[vien], grad[vien], minlength=n2) / np.maximum(
        np.bincount(nhan2[vien], minlength=n2), 1)
    # Trung vi do sac mep: bong/nep ao (mu hoodie, nach) mep mem, chi vai doan duong may sac
    # -> trung binh bi doi len nhung trung vi van thap; net in sac gan het vien.
    lv, gv = nhan2[vien], grad[vien]
    thu_tu = np.lexsort((gv, lv))
    dem_v = np.bincount(lv, minlength=n2)
    dau = np.concatenate([[0], np.cumsum(dem_v)[:-1]])
    mep_tv = (np.where(dem_v > 0, gv[thu_tu][np.minimum(dau + dem_v // 2, len(gv) - 1)], 0)
              if len(gv) else np.zeros(n2))
    ung = [i for i in range(1, n2) if i not in cham_bien]
    nguong_mep = nguong_tv = 0.0
    if ung:  # nguong mep: 80, ha xuong neu ca design tuong phan thap
        nguong_mep = min(80.0, 0.3 * float(np.average(mep[ung], weights=dien_tich[ung])))
        nguong_tv = 0.4 * float(np.average(mep_tv[ung], weights=dien_tich[ung]))
    # chi loai theo trung vi khi khoi giong bong: cung sac do mau ao, chi toi hon vua phai (khong phai muc den)
    bong = np.zeros(n2, bool)
    if nen is not None:
        lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
        ln = lab_cua(nen)
        dab = np.hypot(lab[..., 1] - ln[..., 1], lab[..., 2] - ln[..., 2])
        dL = ln[..., 0] - lab[..., 0]
        sl = np.maximum(dien_tich, 1)
        dab_tb = np.bincount(nhan2.ravel(), dab.ravel(), minlength=n2) / sl
        dL_tb = np.bincount(nhan2.ravel(), dL.ravel(), minlength=n2) / sl
        bong = (dab_tb < 8) & (dL_tb > 0) & (dL_tb < 110)
    giu = [i for i in ung if dam_nhat[i] >= 0.9 and mep[i] >= nguong_mep
           and (mep_tv[i] >= nguong_tv or not bong[i])
           and (dien_tich[i] >= 40 or dam_nhat[i] >= 0.99)]
    lo = np.isin(nhan2, giu)
    # Cuu net chu dinh vao bong/nach ao qua mang rong (cau day, mo nho khong cat duoc):
    # mo bang nhan to (~1/40 anh) chi con than nguoi/bong; phan ra-bien con lai la net manh.
    # Giu manh net mep sac, dam, nam trong khung design chinh.
    if lo.any():
        K = max(9, round(min(h, w) / 40)) | 1
        than = cv2.morphologyEx(ra_bien, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (K, K)))
        than = cv2.dilate(than, np.ones((5, 5), np.uint8))
        manh = (ra_bien & (1 - than)).astype(np.uint8)
        ys, xs = np.nonzero(lo)
        lx1, lx2, ly1, ly2 = xs.min(), xs.max(), ys.min(), ys.max()
        d = 0.02 * max(lx2 - lx1, ly2 - ly1)
        khung = np.zeros_like(manh)
        khung[max(int(ly1 - d), 0):int(ly2 + d) + 1, max(int(lx1 - d), 0):int(lx2 + d) + 1] = 1
        manh &= khung
        nm2, nh_m, tk_m, _ = cv2.connectedComponentsWithStats(manh)
        if nm2 > 1:
            dm = np.zeros(nm2, np.float32)
            np.maximum.at(dm, nh_m.ravel(), alpha.ravel())
            nfm = nh_m.astype(np.float32)
            vm = cv2.dilate(nfm, np.ones((3, 3))) != cv2.erode(nfm, np.ones((3, 3)))
            mep_m = np.bincount(nh_m[vm], grad[vm], minlength=nm2) / np.maximum(
                np.bincount(nh_m[vm], minlength=nm2), 1)
            # chi cuu manh sat design chinh (cach <= 2 lan net mo nho), khong lay mep ao/tay o xa
            sat = cv2.dilate(lo.astype(np.uint8), np.ones((2 * k + 1, 2 * k + 1), np.uint8))
            sat_lo = np.bincount(nh_m.ravel(), sat.ravel(), minlength=nm2) > 0
            cuu = [i for i in range(1, nm2)
                   if tk_m[i, 4] >= 40 and dm[i] >= 0.9 and mep_m[i] >= max(nguong_mep, 60) and sat_lo[i]]
            if cuu:
                lo = lo | np.isin(nh_m, cuu)
    # noi lai cac lo gan nhau, giu cum lon nhat (design chinh)
    gop = cv2.dilate(lo.astype(np.uint8), np.ones((31, 31), np.uint8))
    n3, nhan3, tk3, _ = cv2.connectedComponentsWithStats(gop)
    if n3 <= 1:
        return alpha * 0
    # cum phu (dong chu/hinh tach xa: moi, chu duoi) giu neu >= 1% cum chinh, tam nam trong cot ngang cum chinh
    # va cach cum chinh <= 35% chieu cao; toc/tay/day mu nam lech cot hoac xa -> bo
    kl3 = np.bincount(nhan3[lo], minlength=n3)
    kl3[0] = 0
    lon = kl3.argmax()
    bx, by, bw, bh = tk3[lon, :4]
    giu3 = [lon]
    for i in np.nonzero(kl3 >= 0.01 * kl3[lon])[0]:
        if i == lon:
            continue
        x, y, ww, hh = tk3[i, :4]
        cach = max(by - (y + hh), y - (by + bh), 0)
        tren_hep = y + hh <= by and ww < 0.25 * bw  # mac/nhan co ao phia tren design
        if bx <= x + ww / 2 <= bx + bw and cach <= 0.35 * bh and not tren_hep:
            giu3.append(i)
    # no them 2px de giu mep mem (alpha < 0.5) quanh net design
    giu_lai = cv2.dilate((lo & np.isin(nhan3, giu3)).astype(np.uint8), np.ones((5, 5), np.uint8))
    return alpha * giu_lai


def bo_vien_nen(rgb, alpha, nen):
    a = alpha[..., None]
    f = rgb.astype(np.float32)
    mau = (f - (1 - a) * nen.astype(np.float32)) / np.maximum(a, 1e-3)
    return np.clip(mau, 0, 255)


MO_HINH = {  # tai ve tool\mo-hinh\ (khong dua len git)
    "minh-hoa": ("RealESRGAN_x4plus_anime_6B.pth", 6,
                 "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth"),
    "anh-that": ("RealESRGAN_x4plus.pth", 23,
                 "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"),
}


def phong_to_ai(rgb, loai, o=256, chong=16):
    """Real-ESRGAN x4 (kien truc RRDBNet), chay tung o de vua VRAM."""
    import torch
    from torch import nn
    import torch.nn.functional as F

    class RDB(nn.Module):
        def __init__(s, nf=64, gc=32):
            super().__init__()
            s.conv1 = nn.Conv2d(nf, gc, 3, 1, 1)
            s.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1)
            s.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1)
            s.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1)
            s.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1)

        def forward(s, x):
            r = lambda t: F.leaky_relu(t, 0.2)
            x1 = r(s.conv1(x))
            x2 = r(s.conv2(torch.cat((x, x1), 1)))
            x3 = r(s.conv3(torch.cat((x, x1, x2), 1)))
            x4 = r(s.conv4(torch.cat((x, x1, x2, x3), 1)))
            return s.conv5(torch.cat((x, x1, x2, x3, x4), 1)) * 0.2 + x

    class RRDB(nn.Module):
        def __init__(s):
            super().__init__()
            s.rdb1, s.rdb2, s.rdb3 = RDB(), RDB(), RDB()

        def forward(s, x):
            return s.rdb3(s.rdb2(s.rdb1(x))) * 0.2 + x

    class RRDBNet(nn.Module):
        def __init__(s, nb):
            super().__init__()
            s.conv_first = nn.Conv2d(3, 64, 3, 1, 1)
            s.body = nn.Sequential(*[RRDB() for _ in range(nb)])
            s.conv_body = nn.Conv2d(64, 64, 3, 1, 1)
            s.conv_up1 = nn.Conv2d(64, 64, 3, 1, 1)
            s.conv_up2 = nn.Conv2d(64, 64, 3, 1, 1)
            s.conv_hr = nn.Conv2d(64, 64, 3, 1, 1)
            s.conv_last = nn.Conv2d(64, 3, 3, 1, 1)

        def forward(s, x):
            r = lambda t: F.leaky_relu(t, 0.2)
            f = s.conv_first(x)
            f = f + s.conv_body(s.body(f))
            f = r(s.conv_up1(F.interpolate(f, scale_factor=2, mode="nearest")))
            f = r(s.conv_up2(F.interpolate(f, scale_factor=2, mode="nearest")))
            return s.conv_last(r(s.conv_hr(f)))

    ten, nb, url = MO_HINH[loai]
    duong = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mo-hinh", ten)
    if not os.path.exists(duong):
        raise SystemExit(f"Thieu mo hinh {duong}\nTai: curl.exe -L -o \"{duong}\" {url}")
    may = "cuda" if torch.cuda.is_available() else "cpu"
    net = RRDBNet(nb)
    sd = torch.load(duong, map_location="cpu", weights_only=True)
    net.load_state_dict(sd.get("params_ema", sd.get("params", sd)))
    net = net.eval().to(may)
    if may == "cuda":
        net = net.half()

    h, w = rgb.shape[:2]
    ra = np.zeros((h * 4, w * 4, 3), np.float32)
    x = torch.from_numpy(rgb.astype(np.float32) / 255).permute(2, 0, 1)[None]
    with torch.no_grad():
        for y0 in range(0, h, o):
            for x0 in range(0, w, o):
                ya, xa = max(y0 - chong, 0), max(x0 - chong, 0)
                yb, xb = min(y0 + o + chong, h), min(x0 + o + chong, w)
                t = x[:, :, ya:yb, xa:xb].to(may)
                t = t.half() if may == "cuda" else t
                kq = net(t).float().clamp(0, 1)[0].permute(1, 2, 0).cpu().numpy()
                ye, xe = min(y0 + o, h), min(x0 + o, w)
                ra[y0 * 4:ye * 4, x0 * 4:xe * 4] = kq[(y0 - ya) * 4:(ye - ya) * 4, (x0 - xa) * 4:(xe - xa) * 4]
    return (ra * 255).round().astype(np.uint8)


def chuan_ten(f):
    """Ten de so khop mockup <-> design: bo duoi, 'Gifts For Veteran -', 'T-Shirt', so ' 1', dau cau."""
    import re
    s = os.path.splitext(f)[0].lower().replace("’", "'")
    s = re.sub(r"^gifts for veteran\s*-\s*", "", s)
    s = re.sub(r"\bt-shirt\b", " ", s)
    s = re.sub(r"\s+\d+$", "", s.strip())
    return re.sub(r"[^a-z0-9']+", " ", s).strip()


CAI_DAT = "cai-dat.json"
KHOA_CAI_DAT = {"vung", "xoay", "che", "nguong", "nen", "giu-xam", "giu_xam", "giu-suong", "giu_suong",
                "ai", "giu-ti-le", "giu_ti_le", "le", "bo"}


def doc_cai_dat(thu_muc):
    """cai-dat.json trong thu muc mockup: {"<ten mockup (dau ten la du)>": {"vung": "..", "xoay": -14, "che": [..]}}"""
    import json
    p = os.path.join(thu_muc, CAI_DAT)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        cd = json.load(f)
    cd = {k: v for k, v in cd.items() if not k.startswith("_")}  # khoa "_..." = ghi chu
    for ten, v in cd.items():
        la = set(v) - KHOA_CAI_DAT
        if la:
            raise SystemExit(f"{CAI_DAT}: '{ten}' co khoa la {sorted(la)}; dung duoc: {sorted(KHOA_CAI_DAT)}")
        if isinstance(v.get("che"), str):
            v["che"] = [v["che"]]
    return cd


def cai_dat_cho(cai_dat, f):
    # so ten goc (khong bo "T-Shirt": 2 mockup chi khac nhau o duoi T-Shirt); ten dai nhat khop thang
    def gon(s):
        return " ".join(s.lower().replace("’", "'").split())
    t = gon(os.path.splitext(f)[0])
    khop = [k for k in cai_dat if t.startswith(gon(k))]
    return dict(cai_dat[max(khop, key=len)]) if khop else {}


def to_xem_lai(thu_muc_anh, thu_muc_ra, o=300):
    """Ghep mockup | design (tren nen toi va nen trang) -> _XEM LAI.jpg de soat nhanh."""
    ds = sorted(f for f in os.listdir(thu_muc_ra) if f.lower().endswith(".png"))
    goc = {os.path.splitext(f)[0]: f for f in os.listdir(thu_muc_anh)
           if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))}
    if not ds:
        return None
    cot = 3
    o = min(o, int(60000 * 7 / 8 / ((len(ds) + cot - 1) // cot)))  # JPEG toi da 65535 px moi chieu
    cao = int(o * 8 / 7)
    W = Image.new("RGB", (cot * o * 3, ((len(ds) + cot - 1) // cot) * cao), (90, 90, 90))
    for i, f in enumerate(ds):
        x0, y0 = (i % cot) * o * 3, (i // cot) * cao
        ten = os.path.splitext(f)[0]
        if ten in goc:
            m = Image.open(os.path.join(thu_muc_anh, goc[ten])).convert("RGB")
            m.thumbnail((o - 6, cao - 6))
            W.paste(m, (x0 + 3, y0 + 3))
        d = Image.open(os.path.join(thu_muc_ra, f)).convert("RGBA")
        d.thumbnail((o - 6, cao - 6))
        for j, mau in enumerate([(35, 35, 35, 255), (245, 245, 245, 255)]):
            b = Image.new("RGBA", d.size, mau)
            b.alpha_composite(d)
            W.paste(b.convert("RGB"), (x0 + o * (j + 1) + 3, y0 + 3))
    ra = os.path.join(thu_muc_ra, "_XEM LAI.jpg")
    W.save(ra, quality=85)
    return ra


def main():
    p = argparse.ArgumentParser(description="Tach design khoi anh ao -> PNG trong suot")
    p.add_argument("anh")
    p.add_argument("-o", "--ra", help="file PNG ra (mac dinh: <ten>_design.png canh anh goc)")
    p.add_argument("--nen", help="mau ao dang #rrggbb (mac dinh: tu do)")
    p.add_argument("--nguong", help="khoang cach mau t1,t2: <t1 trong suot, >t2 dac (mac dinh: tu do theo vai ao)")
    p.add_argument("--vung", help="x1,y1,x2,y2 chi giu vung nay (pixel anh goc)")
    p.add_argument("--le", type=float, default=0.0, help="le trong khung ra, ti le (0.03 = 3%%)")
    p.add_argument("--giu-ti-le", action="store_true",
                   help="giu nguyen ti le design (mac dinh: keo gian tran kin khung 4200x4800)")
    p.add_argument("--nen-xem", action="store_true", help="xuat them anh xem tren nen trang + den")
    p.add_argument("--ai", default="minh-hoa", choices=["minh-hoa", "anh-that", "khong"],
                   help="phong to x4 bang Real-ESRGAN: minh-hoa (design ve, chu) | anh-that | khong")
    p.add_argument("--da-co", help="thu muc design da lam: mockup trung ten (bo T-Shirt, so 1, dau ') thi bo qua")
    p.add_argument("--giu-xam", action="store_true",
                   help="ao toi: KHONG xoa xam toi noi ra ngoai (mac dinh co xoa, de sach van vai heather)")
    p.add_argument("--giu-suong", action="store_true",
                   help="khong xoa mang xam ban trong suot (dung khi design co bong mo xam co y)")
    p.add_argument("--xoay", type=float, default=0,
                   help="xoay anh truoc khi tach, do (duong = nguoc kim dong ho, am = cung chieu)")
    p.add_argument("--che", action="append",
                   help="x1,y1,x2,y2 to mau ao len o nay truoc khi tach (che tay, tuong). Lap lai duoc")
    p.add_argument("--nen-chung", action="store_true",
                   help="dung 1 mau ao cho ca anh (mac dinh: do mau ao theo tung vung, hop anh nguoi mac/sang khong deu)")
    p.add_argument("--chi", type=int, help="chi chay N anh dau (thu nho truoc)")
    p.add_argument("--lam-lai", action="store_true", help="ghi de file da co trong thu muc ra")
    p.add_argument("--luong", type=int, help="so anh chay song song khi chay ca thu muc (mac dinh: tu chon theo may; 1 = lan luot)")
    g = p.parse_args()

    if os.path.isdir(g.anh):  # ca thu muc: moi mockup ra 1 PNG cung ten trong <thu muc>\Design Claude\
        thu_muc_ra = g.ra or os.path.join(g.anh, "Design Claude")
        os.makedirs(thu_muc_ra, exist_ok=True)
        anh = [f for f in sorted(os.listdir(g.anh))
               if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
        cai_dat = doc_cai_dat(g.anh)
        if not g.da_co and os.path.isdir(os.path.join(g.anh, "Design")):
            g.da_co = os.path.join(g.anh, "Design")  # thu muc design anh da lam -> tu bo qua mau trung ten
        if g.da_co:
            co = [chuan_ten(f) for f in os.listdir(g.da_co) if f.lower().endswith(".png")]
            bo = [f for f in anh if any(chuan_ten(f).startswith(c) for c in co if c)]
            anh = [f for f in anh if f not in bo]
            print(f"Bo qua {len(bo)} mau da co design trong {g.da_co}:")
            for f in bo:
                print("  -", f)
        if g.chi:
            anh = anh[:g.chi]
        loi, viec, i = [], [], 0
        for f in anh:
            ra = os.path.join(thu_muc_ra, os.path.splitext(f)[0] + ".png")
            rieng = cai_dat_cho(cai_dat, f)
            if rieng.get("bo") or (os.path.exists(ra) and not g.lam_lai):
                i += 1
                print(f"[{i}/{len(anh)}] {f}")
                print("  cai-dat.json: bo qua" if rieng.get("bo") else "  da co, bo qua")
                continue
            g2 = argparse.Namespace(**vars(g))
            for k, v in rieng.items():
                setattr(g2, k.replace("-", "_"), v)
            viec.append((f, os.path.join(g.anh, f), ra, g2, rieng))

        def bao(f, chu, e):
            nonlocal i
            i += 1
            print(f"[{i}/{len(anh)}] {f}")
            print(chu, end="", flush=True)
            if e:
                loi.append(f)
                print("  LOI:", e, flush=True)

        if not g.luong:
            g.luong = so_luong_tu_chon()
            print(f"Chay song song {g.luong} anh")
        if g.luong > 1 and len(viec) > 1:
            from concurrent.futures import ProcessPoolExecutor, as_completed
            with ProcessPoolExecutor(min(g.luong, len(viec))) as ex:
                tl = {ex.submit(_lam_mot, v[1:]): v[0] for v in viec}
                for fu in as_completed(tl):
                    try:
                        chu, e = fu.result()
                    except Exception as x:  # tien trinh con chet (het bo nho...)
                        chu, e = "", repr(x)
                    bao(tl[fu], chu, e)
        else:
            for v in viec:
                bao(v[0], *_lam_mot(v[1:]))
        print(f"Xong {len(anh) - len(loi)}/{len(anh)} anh -> {thu_muc_ra}" + (f" | loi: {loi}" if loi else ""))
        xem = to_xem_lai(g.anh, thu_muc_ra)
        if xem:
            print("To xem lai:", xem)
    else:
        chay(g.anh, g.ra or os.path.splitext(g.anh)[0] + "_design.png", g)


def so_luong_tu_chon():
    """Moi luong ~2,5 GB bo nho card + ~4 nhan CPU + ~2 GB RAM."""
    nhan = max(1, (os.cpu_count() or 4) // 4)
    try:
        import torch
        if torch.cuda.is_available():
            vram = torch.cuda.get_device_properties(0).total_memory / 2 ** 30
            return int(max(1, min(4, nhan, (vram - 1) // 2.6)))
    except Exception:
        pass
    return int(max(1, min(2, nhan)))


def _lam_mot(viec):
    """Tach 1 anh (chay duoc trong tien trinh con): tra (chu in ra, loi hoac None)."""
    import contextlib, io
    duong, ra, g2, rieng = viec
    buf = io.StringIO()
    e = None
    with contextlib.redirect_stdout(buf):
        if rieng:
            print("  cai rieng:", rieng)
        try:
            chay(duong, ra, g2)
        except (SystemExit, Exception) as x:
            e = str(x) or repr(x)
    return buf.getvalue(), e


def don_xam(im, L_max=140, sac_max=15, a_mo=0.5):
    """Ao toi: xoa mau xam toi trung tinh (van vai heather) noi ra vung trong suot.
    Net den nam trong mang sang (chu den tren bang ron trang) khong noi ra ngoai nen duoc giu."""
    a = im[..., 3].astype(np.float32) / 255
    lab = cv2.cvtColor(np.ascontiguousarray(im[..., :3]), cv2.COLOR_RGB2LAB).astype(np.float32)
    L, sac = lab[..., 0], np.hypot(lab[..., 1] - 128, lab[..., 2] - 128)
    sang = (a > 0.9) & (L > 170)
    gan_sang = cv2.dilate(sang.astype(np.uint8), np.ones((7, 7), np.uint8)) > 0
    rac = (sac < sac_max) & (a > 0.02) & ((L < L_max) | ((a < a_mo) & ~gan_sang))
    ngoai = a <= 0.02
    _, nhan = cv2.connectedComponents((rac | ngoai).astype(np.uint8), connectivity=8)
    xoa = rac & np.isin(nhan, np.unique(nhan[ngoai]))
    ra = im.copy()
    ra[..., 3][xoa] = 0
    # dom le con sot (cum nho tach roi)
    n, nhan, tk, _ = cv2.connectedComponentsWithStats((ra[..., 3] > 5).astype(np.uint8), connectivity=8)
    nho = np.nonzero(tk[:, 4] < max(20, 400 * (im.shape[0] / H_OUT) ** 2))[0]
    ra[..., 3][np.isin(nhan, nho[nho > 0])] = 0
    return ra, xoa.mean()


def chay(duong_anh, ra, g):
    rgb = np.array(Image.open(duong_anh).convert("RGB"))
    if g.che:  # to mau ao len cho dinh tay/tuong (toa do anh goc, truoc khi xoay)
        o_che = [tuple(int(v) for v in str(o).split(",")) for o in g.che]
        mau_che = doc_mau(g.nen) if g.nen else nguong_tu_dong(rgb)[0]
        for lan in range(1 if g.nen else 2):  # lan 2: to lai bang mau ao do tren anh da to -> khop nguong
            for x1, y1, x2, y2 in o_che:
                rgb[y1:y2, x1:x2] = mau_che
            if not g.nen:
                mau_che = nguong_tu_dong(rgb)[0]
    if g.xoay:  # xoay thang design chup nghieng; duong = nguoc kim dong ho. --vung tinh tren anh da xoay
        h, w = rgb.shape[:2]
        M = cv2.getRotationMatrix2D((w / 2, h / 2), g.xoay, 1.0)
        rgb = cv2.warpAffine(rgb, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    nen, t1, t2 = nguong_tu_dong(rgb, doc_mau(g.nen) if g.nen else None)
    if g.nguong:
        t1, t2 = (float(x) for x in g.nguong.split(","))
    vung = [int(x) for x in g.vung.split(",")] if g.vung else None
    nen_chung = nen  # mau ao trung binh (xet ao toi/sang)
    if not getattr(g, "nen_chung", False) and not g.nen:
        nb, t1b, t2b = nen_cuc_bo(rgb, nen, t1, t2)
        nen = nb
        if not g.nguong:
            t1, t2 = t1b, t2b

    alpha = do_trong_suot(rgb, nen, t1, t2)
    alpha = giu_khoi_design(alpha, vung, rgb, nen)
    if not g.giu_suong:
        alpha = bo_suong(rgb, alpha, nen, 5)
        # sau khi xoa suong, manh le xa khoi chinh (vet xuoc, nep vai) -> bo
        # (chi bo cum nho: khoi luong < 2% cum lon nhat; dong chu rieng le van giu)
        gan = cv2.dilate((alpha > 0.3).astype(np.uint8), np.ones((25, 25), np.uint8))
        n, nhan = cv2.connectedComponents(gan)
        if n > 2:
            kl = np.bincount(nhan.ravel(), alpha.ravel(), minlength=n)
            kl[0] = 0
            alpha = alpha * np.isin(nhan, np.nonzero(kl >= 0.02 * kl.max())[0])
    alpha[alpha < 0.04] = 0
    mau = bo_vien_nen(rgb, alpha, nen)

    ys, xs = np.nonzero(alpha > 0.04)
    if not len(xs):
        raise SystemExit("Khong tim thay design - thu ha --nguong hoac dat --nen")
    x1, x2, y1, y2 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    rgba = np.dstack([mau, alpha * 255])[y1:y2, x1:x2].astype(np.float32)

    if g.ai != "khong":
        # Phong to x4 bang AI tren anh chup (con nen ao), roi tach nen lai o ban to
        dem = 16
        X1, Y1 = max(x1 - dem, 0), max(y1 - dem, 0)
        X2, Y2 = min(x2 + dem, rgb.shape[1]), min(y2 + dem, rgb.shape[0])
        to4 = phong_to_ai(rgb[Y1:Y2, X1:X2], g.ai)
        nen4 = nen if nen.ndim == 1 else cv2.resize(np.ascontiguousarray(nen[Y1:Y2, X1:X2]),
                                                    (to4.shape[1], to4.shape[0]), interpolation=cv2.INTER_LINEAR)
        vung_lo = cv2.dilate((alpha[Y1:Y2, X1:X2] > 0).astype(np.uint8), np.ones((5, 5), np.uint8))
        vung_to = cv2.resize(vung_lo.astype(np.float32), (to4.shape[1], to4.shape[0]),
                             interpolation=cv2.INTER_LINEAR)
        a4 = do_trong_suot(to4, nen4, t1, t2) * np.clip(vung_to, 0, 1)
        if not g.giu_suong:
            a4 = bo_suong(to4, a4, nen4, 15)
        a4[a4 < 0.04] = 0
        m4 = bo_vien_nen(to4, a4, nen4)
        k = 4
        rgba = np.dstack([m4, a4 * 255])[(y1 - Y1) * k:(y2 - Y1) * k, (x1 - X1) * k:(x2 - X1) * k]
        rgba = rgba.astype(np.float32)

    if float(np.mean(nen_chung)) < 70 and not g.giu_xam:
        # Ao toi (den heather): van vai lot vao thanh dom/vien xam -> xoa xam toi noi ra ngoai, cat sat lai
        rgba, ti = don_xam(rgba.round().clip(0, 255).astype(np.uint8))
        ys, xs = np.nonzero(rgba[..., 3] > 10)
        rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32)
        print(f"Don xam toi: xoa {ti * 100:.1f}% dien tich")

    # Don cuoi: dom/vet mo nho xa khoi chinh (mep ao, nep vai) lam khung cat rong ra -> bo, cat sat lai
    al = rgba[..., 3]
    r = max(3, round(max(al.shape) / 20)) | 1
    gan = cv2.dilate((al > 25).astype(np.uint8), np.ones((r, r), np.uint8))
    n_c, nh_c = cv2.connectedComponents(gan)
    if n_c > 2:
        kl = np.bincount(nh_c.ravel(), al.ravel(), minlength=n_c)
        kl[0] = 0
        giu_c = np.isin(nh_c, np.nonzero(kl >= 0.01 * kl.sum())[0])
        rgba[~giu_c] = 0
    ys, xs = np.nonzero(rgba[..., 3] > 10)
    rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

    # Lan 2, noi net nho: soi toc / vet mo nho nam NGOAI khung khoi chinh (keo lech khung cat) -> bo.
    # Hoa tiet nho cua design (sao, bong tuyet) nam trong khung khoi chinh nen van giu.
    al = rgba[..., 3]
    r2 = max(3, round(max(al.shape) / 60)) | 1
    gan = cv2.dilate((al > 25).astype(np.uint8), np.ones((r2, r2), np.uint8))
    n_c, nh_c, tk_c, _ = cv2.connectedComponentsWithStats(gan)
    if n_c > 2:
        kl = np.bincount(nh_c.ravel(), al.ravel(), minlength=n_c)
        kl[0] = 0
        lon = [i for i in range(1, n_c) if kl[i] >= 0.03 * kl.sum()]
        if lon:
            kx1 = min(tk_c[i][0] for i in lon); ky1 = min(tk_c[i][1] for i in lon)
            kx2 = max(tk_c[i][0] + tk_c[i][2] for i in lon); ky2 = max(tk_c[i][1] + tk_c[i][3] for i in lon)
            bo = []
            for i in range(1, n_c):
                if i in lon or kl[i] >= 0.005 * kl.sum():
                    continue
                x, y, w, h = tk_c[i][:4]
                trong = max(0, min(x + w, kx2) - max(x, kx1)) * max(0, min(y + h, ky2) - max(y, ky1))
                if trong < 0.5 * w * h:
                    bo.append(i)
            if bo:
                rgba[np.isin(nh_c, bo)] = 0
                ys, xs = np.nonzero(rgba[..., 3] > 10)
                rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]

    # Phong to: nhan mau voi alpha truoc khi resize de mep khong ra quang mau
    tl = min(W_OUT * (1 - 2 * g.le) / rgba.shape[1], H_OUT * (1 - 2 * g.le) / rgba.shape[0])
    nw, nh = round(rgba.shape[1] * tl), round(rgba.shape[0] * tl)
    if not g.giu_ti_le:  # tran kin khung
        nw, nh = round(W_OUT * (1 - 2 * g.le)), round(H_OUT * (1 - 2 * g.le))
    a = rgba[..., 3:] / 255
    pre = np.dstack([rgba[..., :3] * a, a * 255])
    to = cv2.resize(pre, (nw, nh), interpolation=cv2.INTER_LANCZOS4)
    if g.ai == "khong":
        mo = cv2.GaussianBlur(to, (0, 0), 2.0)
        to = np.clip(to * 1.6 - mo * 0.6, 0, None)  # lam net nhe
    a2 = np.clip(to[..., 3:] / 255, 0, 1)
    c2 = np.clip(to[..., :3] / np.maximum(a2, 1e-3), 0, 255)
    to = np.dstack([c2, a2 * 255]).round().astype(np.uint8)
    to[to[..., 3] < 3] = 0

    khung = np.zeros((H_OUT, W_OUT, 4), np.uint8)
    ox, oy = (W_OUT - nw) // 2, (H_OUT - nh) // 2
    khung[oy:oy + nh, ox:ox + nw] = to

    Image.fromarray(khung, "RGBA").save(ra, dpi=(300, 300), compress_level=3)
    print(f"Mau ao: #{nen_chung[0]:02x}{nen_chung[1]:02x}{nen_chung[2]:02x} nguong {t1:.0f},{t2:.0f} | design goc {x2 - x1}x{y2 - y1}px "
          f"tai ({x1},{y1}) | phong to x{tl:.2f} -> {nw}x{nh} trong khung {W_OUT}x{H_OUT}")
    print("Da luu:", ra)
    if tl > 2 and g.ai == "khong":
        print(f"Chu y: phong to x{tl:.1f} tu anh chup -> net kem, in ra se mo. Can anh goc lon hon.")

    if g.nen_xem:
        for ten, mau_nen in (("trang", 255), ("den", 20)):
            nho = Image.fromarray(khung, "RGBA").resize((W_OUT // 5, H_OUT // 5), Image.LANCZOS)
            n = Image.new("RGBA", nho.size, (mau_nen,) * 3 + (255,))
            n.alpha_composite(nho)
            n.convert("RGB").save(os.path.splitext(ra)[0] + f"_xem_{ten}.jpg", quality=90)


if __name__ == "__main__":
    main()
