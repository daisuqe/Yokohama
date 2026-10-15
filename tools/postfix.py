"""今のドット絵(48x48)を、ディテールはそのままに、直す。
 1. 黒に近い輪郭の画素 → まわりの塗りの色の「彩度を上げて、少し暗くした色」にする(黒くしない)
 2. 屋根: 光は左上から当たるので、左上を明るく、右下を暗くする
 (壁をそろえる fix_wall も入っているが、今は使っていない。地面(芝生)も、そのまま。)
使い方: python tools/postfix.py <入力フォルダ> <出力フォルダ> [house01 house02 ...]
"""
import sys, os, colorsys
import numpy as np, cv2
from PIL import Image

OL_LUM = 62          # この明るさより暗い画素を「輪郭」とみなす
WALL_LUM = 120       # 壁とみなす明るさの下限


def lum(a):
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def hsv(a):
    x = a.astype(np.float32) / 255
    mx, mn = x.max(-1), x.min(-1)
    d = mx - mn
    s = np.where(mx > 0, d / np.maximum(mx, 1e-6), 0)
    r, g, b = x[..., 0], x[..., 1], x[..., 2]
    h = np.zeros_like(mx)
    m = d > 1e-6
    h = np.where(m & (mx == r), ((g - b) / np.maximum(d, 1e-6)) % 6, h)
    h = np.where(m & (mx == g), (b - r) / np.maximum(d, 1e-6) + 2, h)
    h = np.where(m & (mx == b), (r - g) / np.maximum(d, 1e-6) + 4, h)
    return h / 6, s, mx


def edge_color(c):
    """塗りの色の彩度を上げて、少し暗くした色 (黒にはしない)"""
    r, g, b = [v / 255 for v in c]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = min(1, s * 1.3 + .08); v = v * .78
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return np.array([r * 255, g * 255, b * 255])


def fix_outline(a):
    al = a[:, :, 3] > 128
    L = lum(a[:, :, :3])
    dark = al & (L < OL_LUM)
    fill = al & ~dark
    out = a.copy()
    H, W = L.shape
    for y, x in zip(*np.where(dark)):
        for r in (1, 2, 3):                                     # いちばん近い「塗り」の色を、まわりから集める
            ys, xs = slice(max(0, y - r), y + r + 1), slice(max(0, x - r), x + r + 1)
            m = fill[ys, xs]
            if m.any():
                c = a[ys, xs, :3][m].astype(np.float32).mean(0)
                out[y, x, :3] = np.clip(edge_color(c), 0, 255).astype(np.uint8)
                break
    return out, dark


def fix_wall(a, protect):
    """壁の画素(明るくて彩度が低い暖色)を、2〜3色にそろえて、孤立したドットをなくす"""
    al = a[:, :, 3] > 128
    h, s, v = hsv(a[:, :, :3])
    L = lum(a[:, :, :3])
    wall = al & ~protect & (L > WALL_LUM) & (s < .5) & (h > .04) & (h < .2)
    if wall.sum() < 20:
        return a
    pts = a[:, :, :3][wall].astype(np.float32)
    k = 3
    cv2.setRNGSeed(3)
    _, lab, cen = cv2.kmeans(pts, k, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, .2), 4, cv2.KMEANS_PP_CENTERS)
    lab = lab.ravel()
    L2 = -np.ones(wall.shape, np.int32); L2[wall] = lab
    for _ in range(2):                                          # まわりの多数派にそろえる(まだらを消す)
        pad = np.pad(L2, 1, constant_values=-1)
        new = L2.copy()
        for y, x in zip(*np.where(wall)):
            nb = np.array([pad[y + 1 + dy, x + 1 + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1)])
            nb = nb[nb >= 0]
            new[y, x] = np.bincount(nb, minlength=k).argmax()
        L2 = new
    out = a.copy()
    for y, x in zip(*np.where(wall)):
        out[y, x, :3] = np.clip(cen[L2[y, x]], 0, 255).astype(np.uint8)
    return out


def fix_roof_light(a, hi=1.55, lo=.92):
    """青い屋根の明るさに、左上→右下のグラデーションを付ける(光は左上から)"""
    al = a[:, :, 3] > 128
    h, s, v = hsv(a[:, :, :3])
    L = lum(a[:, :, :3])
    roof = al & (h > .55) & (h < .72) & (s > .25) & (L < 135)
    if roof.sum() < 20:
        return a
    ys, xs = np.where(roof)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    out = a.copy().astype(np.float32)
    for y, x in zip(ys, xs):
        t = (((x - x0) / max(1, x1 - x0)) + ((y - y0) / max(1, y1 - y0))) / 2          # 0=左上, 1=右下
        m = hi + (lo - hi) * t
        out[y, x, :3] = np.clip(out[y, x, :3] * m, 0, 255)
    return out.astype(np.uint8)


def process(path):
    a = np.array(Image.open(path).convert('RGBA'))
    a, dark = fix_outline(a)
    a = fix_roof_light(a)
    return Image.fromarray(a, 'RGBA')


if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    names = sys.argv[3:] or [f[:-4] for f in sorted(os.listdir(src)) if f.endswith('.png')]
    os.makedirs(dst, exist_ok=True)
    for n in names:
        process(os.path.join(src, n + '.png')).save(os.path.join(dst, n + '.png'))
        print(n)
