"""高解像度の絵 → 48x48 のドット絵 (住宅用サンプル)。
 - 下の位置・大きさ: 透明でない範囲の幅を48pxに合わせ、下端をそろえる(今のアイコンと同じ配置)
 - 色: 少数のパレットにまとめる(壁のまだらを防ぐ)。黒い輪郭線は、まわりの塗りの色で埋める
 - 縮小: 4x4 の区画ごとに、いちばん多い色を採る(平均はしない=色がにじまない)
 - 仕上げ: 孤立した1ドットを消す。外周は、塗りの色の「彩度を上げて少し暗くした色」で縁取る
"""
import sys, csv, colorsys
import numpy as np, cv2
from PIL import Image

OL_FRAC = .2
T = 48          # 出力の幅・高さ
Q = 4           # 作業は 4倍 (192px) で行う


def load(path):
    im = np.array(Image.open(path).convert('RGBA'))
    a = im[:, :, 3] > 128
    ys, xs = np.where(a)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    return im[y0:y1, x0:x1]


def shrink(im, h_out):
    """アルファで重みを付けた縮小 (縁に色が混ざらない)"""
    a = im[:, :, 3:4].astype(np.float32) / 255
    rgb = im[:, :, :3].astype(np.float32) * a
    size = (T * Q, h_out * Q)
    rgb = cv2.resize(rgb, size, interpolation=cv2.INTER_AREA)
    a2 = cv2.resize(a, size, interpolation=cv2.INTER_AREA)
    if a2.ndim == 2:
        a2 = a2[:, :, None]
    col = rgb / np.maximum(a2, 1e-3)
    return np.clip(col, 0, 255), a2[:, :, 0]


def palette(col, opaque, k=18, merge=26):
    pts = col[opaque].astype(np.float32)
    k = min(k, len(pts))
    cv2.setRNGSeed(1)
    _, lab, cen = cv2.kmeans(pts, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, .2), 3, cv2.KMEANS_PP_CENTERS)
    cen = cen.copy()
    # 近い色は、ひとつにまとめる (壁の白がまだらに分かれないように)
    cnt = np.bincount(lab.ravel(), minlength=k).astype(np.float64)
    alive = list(range(k))
    changed = True
    while changed:
        changed = False
        for i in alive:
            for j in alive:
                if j <= i:
                    continue
                if np.linalg.norm(cen[i] - cen[j]) < merge:
                    cen[i] = (cen[i] * cnt[i] + cen[j] * cnt[j]) / (cnt[i] + cnt[j]); cnt[i] += cnt[j]
                    alive.remove(j); changed = True
                    break
            if changed:
                break
    cen = cen[alive]
    d = np.linalg.norm(col[:, :, None, :] - cen[None, None, :, :], axis=3)
    return d.argmin(axis=2), cen


def lum(c):
    return 0.299 * c[..., 0] + 0.587 * c[..., 1] + 0.114 * c[..., 2]


def fill_dark(lbl, dark, opaque):
    """黒い輪郭の画素を、いちばん近い塗りのラベルで埋める"""
    lbl = lbl.copy(); lbl[dark] = -1
    H, W = lbl.shape
    for _ in range(12):
        todo = (lbl < 0) & opaque
        if not todo.any():
            break
        pad = np.pad(lbl, 1, constant_values=-1)
        new = lbl.copy()
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (1, -1), (-1, 1), (-1, -1)):
            nb = pad[1 + dy:1 + dy + H, 1 + dx:1 + dx + W]
            m = (new < 0) & todo & (nb >= 0)
            new[m] = nb[m]
        lbl = new
    return lbl


def mode_down(lbl, opaque, n):
    H, W = lbl.shape
    h, w = H // Q, W // Q
    out = -np.ones((h, w), np.int32)
    for y in range(h):
        for x in range(w):
            o = opaque[y * Q:(y + 1) * Q, x * Q:(x + 1) * Q]
            if o.sum() * 2 < Q * Q:
                continue
            b = lbl[y * Q:(y + 1) * Q, x * Q:(x + 1) * Q][o]
            b = b[b >= 0]
            if len(b):
                out[y, x] = np.bincount(b, minlength=n).argmax()
    return out


def cleanup(lbl, n, thr=1):
    """まわりに同じ色がない(孤立した)ドットを、まわりでいちばん多い色にする"""
    H, W = lbl.shape
    for _ in range(2):
        pad = np.pad(lbl, 1, constant_values=-1)
        new = lbl.copy()
        for y in range(H):
            for x in range(W):
                v = lbl[y, x]
                if v < 0:
                    continue
                nb = np.array([pad[y + 1 + dy, x + 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dy or dx])
                same = (nb == v).sum()
                if same <= thr:
                    nb = nb[nb >= 0]
                    if len(nb):
                        new[y, x] = np.bincount(nb, minlength=n).argmax()
        lbl = new
    return lbl


def edge_color(c):
    """縁取りの色: 塗りの色の彩度を上げて、少し暗くしたもの (黒にはしない)"""
    r, g, b = [v / 255 for v in c]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = min(1, s * 1.25 + .06); v = v * .8
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def grade(c):
    """彩度を少し上げる (芝生の緑は、今のアイコンの鮮やかさに合わせて強めに)"""
    r, g, b = [v / 255 for v in c]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = min(1, s * (1.5 if .17 < h < .45 else 1.12))
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return np.array([r * 255, g * 255, b * 255])


def pixelize(path, outline=True, k=48, merge=8):
    im = load(path)
    bh, bw = im.shape[:2]
    h_out = min(T, max(1, round(bh * T / bw)))
    col, a = shrink(im, h_out)                                  # 192幅 (4倍) で下ごしらえ
    opaque = a > .5
    rgb = np.clip(col, 0, 255).astype(np.uint8)
    rgb = cv2.bilateralFilter(rgb, 5, 10, 3)                      # 質感だけをならす (輪郭・窓の縁は残る)
    lbl, cen = palette(np.clip(rgb, 0, 255).astype(np.float32), opaque, k=k, merge=merge)
    dark = (lum(cen)[lbl] < 52) & opaque                        # 黒に近い画素 = 輪郭線 → まわりの塗りの色で埋める
    lbl = fill_dark(lbl, dark, opaque)
    low = mode_down(lbl, opaque, len(cen))
    low = cleanup(low, len(cen), 0)
    # 輪郭線(黒に近い画素)が区画の3割以上を占めるドットは、「その塗りの色を、彩度高く少し暗くした色」の線にする
    H4, W4 = dark.shape
    ol = np.zeros(low.shape, bool)
    for y in range(low.shape[0]):
        for x in range(low.shape[1]):
            o = opaque[y*Q:(y+1)*Q, x*Q:(x+1)*Q]
            if low[y, x] >= 0 and o.sum() and dark[y*Q:(y+1)*Q, x*Q:(x+1)*Q][o].sum() >= OL_FRAC * o.sum():
                ol[y, x] = True
    cen = np.array([grade(c) for c in cen])
    out = np.zeros((T, T, 4), np.uint8)
    y0 = T - h_out
    for y in range(h_out):
        for x in range(T):
            v = low[y, x]
            if v >= 0:
                c = edge_color(cen[v]) if ol[y, x] else [int(round(t)) for t in cen[v]]
                out[y0 + y, x] = (*c, 255)
    if outline:                                                 # 外周を、塗りの色から作った縁取りにする
        al = out[:, :, 3] > 0
        pad = np.pad(al, 1, constant_values=False)
        edge = al & ~(pad[0:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, 0:-2] & pad[1:-1, 2:])
        src = out.copy()
        for y, x in zip(*np.where(edge)):
            out[y, x, :3] = edge_color(src[y, x, :3])
    return Image.fromarray(out, 'RGBA')


if __name__ == '__main__':
    pixelize(sys.argv[1]).save(sys.argv[2])
