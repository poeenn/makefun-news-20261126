# -*- coding: utf-8 -*-
"""26 November 2026 の世界ニュースを1枚のポスター画像にまとめるプログラム。

設計方針(従来の新聞1面形式から変更):
- 審査員は画像を約300px幅でも読めることを重視する。そのため文字は大きく、
  物語は「写真パネル」の大きな絵と短い見出しで伝える。
- 構成: リード1件(ウクライナ和平)+ 4つの写真パネル(関税 / 北朝鮮 / クウェート /
  感謝祭パレード)+ 下段に2件(ECB / HIV予防薬)。地域と分野の広さを確保する。
- 標準ライブラリのみ。2倍解像度で描いて縮小するアンチエイリアス付き。
- 決定的出力: 乱数は固定シードの線形合同法のみを使う。
"""
import os
import struct
import zlib

W = 1024
H = 1024
SS = 2  # スーパーサンプリング倍率
SW = W * SS
SH = H * SS

FB = bytearray(SW * SH * 3)


def _set(x, y, color):
    if 0 <= x < SW and 0 <= y < SH:
        i = (y * SW + x) * 3
        FB[i] = color[0]
        FB[i + 1] = color[1]
        FB[i + 2] = color[2]


def fill_rect(x, y, w, h, color):
    """最終解像度座標で矩形を塗る。"""
    x0 = int(x * SS)
    y0 = int(y * SS)
    x1 = int((x + w) * SS)
    y1 = int((y + h) * SS)
    if x1 <= 0 or y1 <= 0 or x0 >= SW or y0 >= SH:
        return
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(SW, x1)
    y1 = min(SH, y1)
    row = bytes(color) * (x1 - x0)
    for yy in range(y0, y1):
        i = (yy * SW + x0) * 3
        FB[i:i + len(row)] = row


def vgrad(x, y, w, h, c_top, c_bottom):
    """縦グラデーション。"""
    steps = int(h * SS)
    for s in range(steps):
        t = s / max(1, steps - 1)
        color = tuple(int(c_top[i] + (c_bottom[i] - c_top[i]) * t) for i in range(3))
        yy = int(y * SS) + s
        if 0 <= yy < SH:
            x0 = max(0, int(x * SS))
            x1 = min(SW, int((x + w) * SS))
            row = bytes(color) * (x1 - x0)
            i = (yy * SW + x0) * 3
            FB[i:i + len(row)] = row


def fill_circle(cx, cy, r, color):
    cx_s = cx * SS
    cy_s = cy * SS
    r_s = r * SS
    x0 = int(cx_s - r_s - 1)
    x1 = int(cx_s + r_s + 1)
    y0 = int(cy_s - r_s - 1)
    y1 = int(cy_s + r_s + 1)
    rr = r_s * r_s
    for yy in range(max(0, y0), min(SH, y1)):
        dy = yy - cy_s
        for xx in range(max(0, x0), min(SW, x1)):
            dx = xx - cx_s
            if dx * dx + dy * dy <= rr:
                _set(xx, yy, color)


def fill_ellipse(cx, cy, rx, ry, color):
    cx_s = cx * SS
    cy_s = cy * SS
    rx_s = rx * SS
    ry_s = ry * SS
    x0 = int(cx_s - rx_s - 1)
    x1 = int(cx_s + rx_s + 1)
    y0 = int(cy_s - ry_s - 1)
    y1 = int(cy_s + ry_s + 1)
    for yy in range(max(0, y0), min(SH, y1)):
        dy = (yy - cy_s) / ry_s
        for xx in range(max(0, x0), min(SW, x1)):
            dx = (xx - cx_s) / rx_s
            if dx * dx + dy * dy <= 1.0:
                _set(xx, yy, color)


def fill_poly(points, color):
    """走査線方式の多角形塗りつぶし。points は最終解像度座標。"""
    pts = [(px * SS, py * SS) for px, py in points]
    ys = [p[1] for p in pts]
    y0 = max(0, int(min(ys)))
    y1 = min(SH - 1, int(max(ys)))
    n = len(pts)
    for yy in range(y0, y1 + 1):
        yc = yy + 0.5
        xs = []
        for i in range(n):
            xa, ya = pts[i]
            xb, yb = pts[(i + 1) % n]
            if ya == yb:
                continue
            if (ya <= yc < yb) or (yb <= yc < ya):
                xs.append(xa + (yc - ya) * (xb - xa) / (yb - ya))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            xa = int(xs[i])
            xb = int(xs[i + 1])
            for xx in range(max(0, xa), min(SW, xb + 1)):
                _set(xx, yy, color)


def thick_line(x1, y1, x2, y2, width, color):
    """円スタンプを並べた太い線(丸い端と継ぎ目)。"""
    length = max(abs(x2 - x1), abs(y2 - y1))
    steps = max(2, int(length * SS / max(1.0, width * 0.35)))
    r = width / 2.0
    for s in range(steps + 1):
        t = s / steps
        fill_circle(x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, r, color)


def polyline(points, width, color):
    for i in range(len(points) - 1):
        thick_line(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1],
                   width, color)


def downscale_png():
    """2x2ボックス平均で縮小し、PNGバイト列を返す。"""
    raw = bytearray()
    for y in range(H):
        raw.append(0)
        for x in range(W):
            r = g = b = 0
            for dy in range(SS):
                base = ((y * SS + dy) * SW + x * SS) * 3
                for dx in range(SS):
                    i = base + dx * 3
                    r += FB[i]
                    g += FB[i + 1]
                    b += FB[i + 2]
            n = SS * SS
            raw += bytes((r // n, g // n, b // n))

    def chunk(ctype, payload):
        c = struct.pack(">I", len(payload)) + ctype + payload
        return c + struct.pack(">I", zlib.crc32(ctype + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


class Lcg:
    """固定シードの決定的な疑似乱数(星や窓明かりの配置用)。"""

    def __init__(self, seed):
        self.state = seed & 0x7FFFFFFF

    def next(self, mod):
        self.state = (self.state * 1103515245 + 12345) & 0x7FFFFFFF
        return self.state % mod


# ---------------------------------------------------------------------------
# 太いストロークフォント(7x10グリッド)。大きな見出しでも読める幾何学サンセリフ。
# 各字形: (送り幅ユニット, [線分列...]) 線分列は (x, y) 点の並び。
# ---------------------------------------------------------------------------
_G = {}


def _g(ch, adv, *strokes):
    _G[ch] = (adv, [list(s) for s in strokes])


_g("A", 8.4, [(0, 10), (3.5, 0), (7, 10)], [(1.3, 6.4), (5.7, 6.4)])
_g("B", 8.4, [(0, 0), (0, 10)], [(0, 0), (4, 0), (5.6, 1.3), (5.6, 3.7), (4, 5), (0, 5)],
   [(0, 5), (4.4, 5), (6.1, 6.4), (6.1, 8.6), (4.4, 10), (0, 10)])
_g("C", 8.4, [(6.6, 2.2), (4.6, 0.3), (2, 0.3), (0.3, 2), (0.3, 8), (2, 9.7), (4.6, 9.7), (6.6, 7.8)])
_g("D", 8.4, [(0, 0), (0, 10)], [(0, 0), (3.8, 0), (6.4, 2.8), (6.4, 7.2), (3.8, 10), (0, 10)])
_g("E", 7.8, [(6.4, 0), (0, 0), (0, 10), (6.4, 10)], [(0, 5), (5, 5)])
_g("F", 7.6, [(6.4, 0), (0, 0), (0, 10)], [(0, 5), (4.8, 5)])
_g("G", 8.6, [(6.6, 2.2), (4.6, 0.3), (2, 0.3), (0.3, 2), (0.3, 8), (2, 9.7), (5, 9.7), (6.6, 8), (6.6, 6), (4.4, 6)])
_g("H", 8.4, [(0, 0), (0, 10)], [(7, 0), (7, 10)], [(0, 5), (7, 5)])
_g("I", 4.6, [(2.3, 0), (2.3, 10)], [(0.2, 0), (4.4, 0)], [(0.2, 10), (4.4, 10)])
_g("J", 7.6, [(7, 0), (7, 7.8), (5.6, 9.7), (2.2, 9.7), (0.4, 8.2)])
_g("K", 8.4, [(0, 0), (0, 10)], [(6.6, 0), (0.9, 4.9)], [(2.1, 4.1), (6.6, 10)])
_g("L", 7.6, [(0, 0), (0, 10), (6.4, 10)])
_g("M", 9.4, [(0, 10), (0, 0), (3.9, 5.2), (7.8, 0), (7.8, 10)])
_g("N", 8.6, [(0, 10), (0, 0), (7.2, 10), (7.2, 0)])
_g("O", 8.8, [(3.9, 0), (6.4, 0.8), (7.4, 3), (7.4, 7), (6.4, 9.2), (3.9, 10), (1.4, 9.2), (0.4, 7), (0.4, 3), (1.4, 0.8), (3.9, 0)])
_g("P", 8.4, [(0, 10), (0, 0), (4.8, 0), (6.5, 1.6), (6.5, 4), (4.8, 5.6), (0, 5.6)])
_g("Q", 8.8, [(3.9, 0), (6.4, 0.8), (7.4, 3), (7.4, 7), (6.4, 9.2), (3.9, 10), (1.4, 9.2), (0.4, 7), (0.4, 3), (1.4, 0.8), (3.9, 0)], [(4.4, 6.8), (7.4, 10)])
_g("R", 8.4, [(0, 10), (0, 0), (4.8, 0), (6.5, 1.6), (6.5, 4), (4.8, 5.6), (0, 5.6)], [(3.4, 5.6), (6.6, 10)])
_g("S", 8.2, [(6.6, 1.6), (4.6, 0.2), (1.9, 0.4), (0.5, 2), (1.1, 4.1), (6, 6), (6.8, 8.1), (5.4, 9.7), (2.4, 10), (0.3, 8.4)])
_g("T", 8.2, [(0.1, 0), (7.1, 0)], [(3.6, 0), (3.6, 10)])
_g("U", 8.4, [(0, 0), (0, 7.4), (1.4, 9.7), (5.6, 9.7), (7, 7.4), (7, 0)])
_g("V", 8.4, [(0, 0), (3.5, 10), (7, 0)])
_g("W", 10.2, [(0, 0), (1.7, 10), (4.2, 3.8), (6.7, 10), (8.4, 0)])
_g("X", 8.2, [(0, 0), (7, 10)], [(7, 0), (0, 10)])
_g("Y", 8.2, [(0, 0), (3.5, 4.6), (7, 0)], [(3.5, 4.6), (3.5, 10)])
_g("Z", 8.2, [(0, 0), (7, 0), (0, 10), (7, 10)])
_g("0", 8.4, [(3.5, 0), (5.9, 0.8), (6.8, 3), (6.8, 7), (5.9, 9.2), (3.5, 10), (1.1, 9.2), (0.2, 7), (0.2, 3), (1.1, 0.8), (3.5, 0)])
_g("1", 6.6, [(1.2, 1.6), (4.2, 0), (4.2, 10)], [(1.2, 10), (6, 10)])
_g("2", 8.2, [(0.5, 2.1), (2, 0.3), (5, 0.3), (6.5, 2), (6.5, 4.1), (0, 10), (7, 10)])
_g("3", 8.2, [(0.5, 1.2), (2.6, 0.2), (5, 0.5), (6.1, 2.6), (4.4, 5), (6.1, 7.4), (5, 9.7), (2.4, 9.8), (0.5, 8.8)])
_g("4", 8.4, [(4.6, 10), (4.6, 0), (0.4, 7.2), (7.2, 7.2)])
_g("5", 8.2, [(6.4, 0), (1, 0), (1, 4.4), (4.4, 4.2), (6.5, 6), (6.5, 8.4), (4.6, 10), (1.2, 9.7), (0.3, 8.4)])
_g("6", 8.4, [(6.2, 1.6), (4.2, 0.3), (1.6, 1.4), (0.3, 5), (1, 8.6), (3, 10), (5.6, 9.4), (6.8, 7.4), (6.4, 5.4), (4.4, 4.4), (0.6, 5.2)])
_g("7", 8.2, [(0, 0), (7, 0), (3.1, 10)])
_g("8", 8.4, [(2.1, 0.3), (5.1, 0.3), (6.3, 1.9), (5, 4.6), (2.2, 4.6), (0.9, 1.9), (2.1, 0.3)],
   [(2.2, 4.6), (5, 4.6), (6.9, 6.6), (6, 9.5), (1.2, 9.5), (0.3, 6.6), (2.2, 4.6)])
_g("9", 8.4, [(1, 8.4), (3, 9.7), (5.6, 8.6), (6.9, 5), (6, 1.4), (4, 0), (1.6, 0.6), (0.3, 2.6), (0.6, 4.6), (2.6, 5.6), (6.4, 4.8)])
_g(" ", 4.6)
_g(":", 4.2, [("dot", 2.1, 2.8)], [("dot", 2.1, 7.6)])
_g(".", 4.2, [("dot", 2.1, 9.2)])
_g(",", 4.6, [(2.6, 7.2), (1.9, 10)])
_g("'", 3.8, [(1.9, 0), (1.9, 2.6)])
_g("-", 6.4, [(0.8, 5), (4.8, 5)])
_g("/", 7.6, [(6.6, 0), (0.6, 10)])
_g("!", 4.6, [(2.3, 0), (2.3, 6.8)], [("dot", 2.3, 9.2)])
_g("?", 8.2, [(0.5, 2.1), (2, 0.3), (5, 0.3), (6.5, 2), (5.9, 4.1), (3.5, 6), (3.5, 7.4)], [("dot", 3.5, 9.4)])
_g("%", 10.0, [("ring", 2.2, 2.2, 1.7)], [("ring", 7.8, 7.8, 1.7)], [(8.6, 0), (1.4, 10)])
_g("+", 7.6, [(3.8, 1.6), (3.8, 8.4)], [(0.4, 5), (7.2, 5)])
_g("•", 5.4, [("dot", 2.7, 5)])
_g("(", 6.0, [(4.6, 0.4), (2.2, 2.4), (2.2, 7.6), (4.6, 9.6)])
_g(")", 6.0, [(1.4, 0.4), (3.8, 2.4), (3.8, 7.6), (1.4, 9.6)])

# 字間を少し詰める(見出しの収まりを良くするため)
for _ch in list(_G):
    _adv, _strokes = _G[_ch]
    _G[_ch] = (_adv * 0.92, _strokes)


def text_width(text, size):
    unit = size / 10.0
    total = 0.0
    for ch in text:
        adv = _G.get(ch, _G[" "])[0]
        total += adv * unit
    return total


def draw_text(x, y, text, size, color, align="left"):
    """y は字形の上端。size は大文字の高さ(px)。"""
    unit = size / 10.0
    w = text_width(text, size)
    if align == "center":
        x -= w / 2.0
    elif align == "right":
        x -= w
    width = max(2.2, size * 0.17)
    pen = x
    for ch in text:
        adv, strokes = _G.get(ch, _G[" "])
        for stroke in strokes:
            if stroke and isinstance(stroke[0], tuple) and isinstance(stroke[0][0], str):
                mark = stroke[0]
                if mark[0] == "dot":
                    fill_circle(pen + mark[1] * unit, y + mark[2] * unit,
                                width * 0.62, color)
                elif mark[0] == "ring":
                    cx = pen + mark[1] * unit
                    cy = y + mark[2] * unit
                    r = mark[3] * unit
                    pts = []
                    for i in range(15):
                        a = 2 * _math.pi * i / 14
                        pts.append((cx + r * _math.cos(a), cy + r * _math.sin(a)))
                    polyline(pts, width, color)
                continue
            pts = [(pen + gx * unit, y + gy * unit) for gx, gy in stroke]
            if len(pts) == 1:
                fill_circle(pts[0][0], pts[0][1], width * 0.62, color)
            else:
                polyline(pts, width, color)
        pen += adv * unit
    return w


def fit_size(text, max_width, base, minimum=20):
    """max_width に収まる最大の文字サイズ(base以下)を返す。"""
    size = base
    while size > minimum and text_width(text, size) > max_width:
        size -= 1
    return size


# 数学関数(決定的で副作用なし)
import math as _math


def _cos(a):
    return _math.cos(a)


def _sin(a):
    return _math.sin(a)


# ---------------------------------------------------------------------------
# 色
# ---------------------------------------------------------------------------
WHITE = (245, 246, 248)
BLACK = (8, 10, 14)
AMBER = (255, 176, 32)
GRAY = (168, 178, 190)
DARKPANEL = (13, 16, 22)


def bezier(p0, p1, p2, n=24):
    pts = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        pts.append((x, y))
    return pts


def lead_scene(x, y, w, h):
    """リード: ウクライナ。夜空とキーウの街並み、ミサイルの軌跡と迎撃の光、
    そして日の出に向かう白い鳩(和平への呼びかけ)。"""
    vgrad(x, y, w, h, (13, 26, 54), (216, 112, 52))
    rng = Lcg(20261126)
    for _ in range(80):  # 星
        sx = x + 8 + rng.next(int(w - 16))
        sy = y + 6 + rng.next(int(h * 0.55))
        fill_circle(sx, sy, 1.6, (205, 216, 235))
    fill_circle(x + 74, y + 52, 24, (238, 238, 214))  # 月
    fill_circle(x + 66, y + 46, 21, (13, 26, 54))
    # 地平の太陽(右)
    fill_circle(x + w - 150, y + h - 96, 86, (255, 166, 77))
    fill_circle(x + w - 150, y + h - 96, 64, (255, 196, 110))
    # ミサイルの軌跡(左上から街へ)
    for (sx, ex) in ((70, 330), (150, 420)):
        pts = bezier((x + sx, y - 6), (x + sx + 130, y + h * 0.42), (x + ex, y + h - 52))
        polyline(pts, 11, (255, 122, 40))
        polyline(pts, 6, (255, 190, 70))
        polyline(pts, 2.6, (255, 246, 220))
        fill_circle(x + ex, y + h - 52, 13, (255, 210, 120))
    # 迎撃の光(街から上空へ)
    for dx in (520, 585, 655):
        thick_line(x + dx, y + h - 44, x + dx - 120, y + 60, 3.2, (150, 222, 255))
    # 爆発の光
    fill_circle(x + 330, y + h - 40, 34, (255, 130, 40))
    fill_circle(x + 330, y + h - 40, 22, (255, 180, 70))
    fill_circle(x + 420, y + h - 38, 24, (255, 150, 55))
    # キーウの街並み(シルエットと窓明かり)
    rng2 = Lcg(1126)
    bx = x + 6
    base = y + h
    while bx < x + w - 40:
        bw = 34 + rng2.next(46)
        bh = 44 + rng2.next(88)
        fill_rect(bx, base - bh, bw, bh, (7, 9, 15))
        for _ in range(7):
            wx = bx + 4 + rng2.next(max(2, bw - 10))
            wy = base - bh + 6 + rng2.next(max(2, bh - 14))
            fill_rect(wx, wy, 3.4, 4.6, (255, 196, 92))
        bx += bw + 5
    fill_rect(x, base - 6, w, 6, (5, 6, 10))
    # 白い鳩(右上、太陽に向かう)
    cx, cy = x + w - 268, y + 108
    fill_poly([(cx - 118, cy + 16), (cx - 58, cy + 34), (cx - 44, cy + 4)], (226, 228, 230))  # 尾
    fill_ellipse(cx, cy + 8, 92, 33, (244, 245, 242))  # 体
    fill_poly([(cx - 52, cy - 2), (cx - 14, cy - 62), (cx + 40, cy - 4)], (250, 250, 247))  # 翼
    fill_poly([(cx - 32, cy + 2), (cx - 2, cy - 38), (cx + 30, cy + 2)], (233, 235, 238))
    fill_circle(cx + 88, cy - 12, 21, (248, 248, 245))  # 頭
    fill_poly([(cx + 106, cy - 16), (cx + 126, cy - 9), (cx + 106, cy - 3)], (255, 150, 40))  # くちばし
    fill_circle(cx + 94, cy - 17, 3.2, (20, 20, 20))  # 目
    thick_line(cx + 118, cy - 4, cx + 152, cy + 16, 3.4, (74, 148, 66))  # オリーブの枝
    for (lx, ly) in ((132, 6), (144, 14), (128, 18)):
        fill_ellipse(cx + lx, cy + ly, 9, 4.6, (92, 176, 84))


def trade_scene(x, y, w, h):
    """関税: 港のクレーンとコンテナの山。"""
    vgrad(x, y, w, h * 0.62, (168, 208, 220), (196, 226, 232))
    fill_rect(x, y + h * 0.62, w, h * 0.38, (13, 70, 90))  # 海
    fill_rect(x, y + h - 16, w, 16, (24, 28, 34))  # 岸壁
    colors = [(224, 64, 64), (240, 158, 64), (38, 150, 140), (232, 196, 76),
              (64, 110, 180), (200, 90, 140)]
    cw, chh, gap = 96, 36, 5
    base = y + h - 16
    idx = 0
    for row in range(3):
        for col in range(3):
            px = x + w - 24 - (3 - col) * (cw + gap)
            py = base - (row + 1) * (chh + gap)
            fill_rect(px - 2, py - 2, cw + 4, chh + 4, (16, 20, 26))
            fill_rect(px, py, cw, chh, colors[idx % len(colors)])
            idx += 1
    # クレーン
    col = (26, 34, 44)
    fill_rect(x + 42, y + 14, 15, h - 30, col)
    fill_rect(x + 30, y + 12, w * 0.52, 13, col)
    thick_line(x + 49, y + 18, x + 150, y + h - 20, 6, col)
    thick_line(x + 210, y + 25, x + 210, y + 96, 4, col)
    fill_rect(x + 162, y + 96, cw, chh, (16, 20, 26))
    fill_rect(x + 164, y + 98, cw - 4, chh - 4, colors[3])
    # 波
    rng = Lcg(77)
    for _ in range(16):
        wx = x + 10 + rng.next(int(w - 30))
        wy = y + h * 0.68 + rng.next(int(h * 0.2))
        thick_line(wx, wy, wx + 22, wy, 2.6, (120, 190, 205))


def korea_scene(x, y, w, h):
    """北朝鮮: ミサイルと核の警告標識。"""
    vgrad(x, y, w, h, (46, 10, 10), (12, 10, 14))
    fill_rect(x, y + h - 26, w, 26, (6, 6, 8))  # 地面
    # 煙(場面の高さに比例)
    for (fx_, fy_, r) in ((0.25, 0.80, 26), (0.18, 0.86, 34), (0.33, 0.87, 30), (0.12, 0.90, 26)):
        fill_circle(x + fx_ * w, y + fy_ * h, r, (96, 96, 104))
    # 炎
    fill_poly([(x + 96, y + h - 62), (x + 128, y + h - 6), (x + 162, y + h - 62)], (255, 122, 30))
    fill_poly([(x + 110, y + h - 60), (x + 129, y + h - 22), (x + 150, y + h - 60)], (255, 196, 60))
    # ミサイル本体(斜め)
    fill_poly([(x + 84, y + 36), (x + 116, y + 28), (x + 168, y + h - 22), (x + 138, y + h - 12)],
              (232, 234, 238))
    fill_poly([(x + 84, y + 36), (x + 116, y + 28), (x + 104, y + 6)], (214, 48, 49))  # 弾頭
    fill_poly([(x + 138, y + h - 12), (x + 112, y + h + 4), (x + 132, y + h - 30)], (150, 156, 166))  # 翼
    fill_poly([(x + 168, y + h - 22), (x + 178, y + h + 2), (x + 152, y + h - 38)], (150, 156, 166))
    thick_line(x + 92, y + 52, x + 142, y + h - 32, 7, (214, 48, 49))  # 帯
    # 警告標識(放射能トレフォイル)
    bx, by = x + w - 108, y + 66
    fill_rect(bx - 5, by + 38, 10, h - 96, (110, 116, 124))  # ポール
    fill_circle(bx, by, 46, (250, 200, 32))
    fill_circle(bx, by, 8, (18, 18, 18))
    import math as _m
    for ang in (90, 210, 330):
        pts = [(bx, by)]
        for da in (-28, -14, 0, 14, 28):
            a = _m.radians(ang + da)
            pts.append((bx + 34 * _m.cos(a), by - 34 * _m.sin(a)))
        fill_poly(pts, (18, 18, 18))


def kuwait_scene(x, y, w, h):
    """クウェート: 燃える石油タンクとドローン。"""
    vgrad(x, y, w, h, (66, 50, 44), (26, 21, 20))
    fill_rect(x, y + h - 18, w, 18, (14, 12, 12))
    # 煙
    for (sx, sy, r) in ((250, 26, 24), (292, 14, 30), (338, 22, 26), (382, 10, 30)):
        fill_circle(x + sx, y + sy, r, (44, 42, 46))
    # タンク3基
    tank_top = y + h - 104
    for i, tx in enumerate((36, 196, 356)):
        fill_rect(x + tx, tank_top, 108, 86, (148, 152, 160))
        fill_ellipse(x + tx + 54, tank_top, 54, 12, (172, 176, 184))
        thick_line(x + tx + 4, tank_top + 30, x + tx + 104, tank_top + 30, 3, (110, 114, 122))
    # 中央タンクの炎(タンク上端から上へ)
    fx = x + 250
    fill_poly([(fx - 40, tank_top + 2), (fx - 8, tank_top - 50), (fx + 14, tank_top - 22),
               (fx + 30, tank_top - 58), (fx + 44, tank_top + 2)], (255, 118, 28))
    fill_poly([(fx - 20, tank_top + 2), (fx + 2, tank_top - 34), (fx + 24, tank_top + 2)],
              (255, 198, 66))
    # ドローン(左上)
    dx, dy = x + 84, y + 52
    fill_rect(dx - 26, dy - 10, 52, 20, (16, 16, 20))
    for (ax, ay) in ((-44, -26), (44, -26), (-44, 26), (44, 26)):
        thick_line(dx, dy, dx + ax, dy + ay, 6, (16, 16, 20))
        fill_ellipse(dx + ax, dy + ay, 17, 5.4, (196, 200, 206))
    fill_circle(dx, dy + 14, 4.6, (255, 60, 50))


def parade_scene(x, y, w, h):
    """感謝祭: 嵐で傾く七面鳥バルーンとニューヨークの街並み。"""
    vgrad(x, y, w, h, (74, 104, 128), (38, 56, 76))
    rng = Lcg(55)  # 雨
    for _ in range(46):
        rx = x + rng.next(int(w))
        ry = y + rng.next(int(h - 30))
        thick_line(rx, ry, rx - 9, ry + 20, 2.2, (168, 198, 218))
    # 風のうねり
    for wy in (44, 84):
        pts = bezier((x + 16, y + wy), (x + 130, y + wy - 22), (x + 250, y + wy + 8), 16)
        polyline(pts, 4, (222, 236, 246))
    # 街並み
    rng2 = Lcg(99)
    bx = x + 4
    while bx < x + w - 30:
        bw = 30 + rng2.next(38)
        bh = 40 + rng2.next(70)
        fill_rect(bx, y + h - bh, bw, bh, (18, 26, 36))
        bx += bw + 6
    fill_rect(x, y + h - 8, w, 8, (10, 14, 20))
    # 七面鳥バルーン(尾羽の扇)
    cx, cy = x + w * 0.52, y + h * 0.52
    fan = [(150, 96, 46), (178, 116, 54), (204, 132, 60), (178, 116, 54), (150, 96, 46)]
    import math as _m
    for i, ang in enumerate((205, 235, 270, 305, 335)):
        a = _m.radians(ang)
        ex = cx + 84 * _m.cos(a)
        ey = cy + 64 * _m.sin(a)
        fill_ellipse(ex, ey, 34, 17, fan[i])
    fill_ellipse(cx, cy, 88, 56, (158, 98, 52))  # 体
    fill_ellipse(cx - 12, cy + 8, 46, 30, (128, 76, 40))  # 翼
    fill_circle(cx + 74, cy - 34, 25, (170, 108, 58))  # 頭
    fill_poly([(cx + 94, cy - 40), (cx + 118, cy - 33), (cx + 94, cy - 27)], (255, 164, 40))  # くちばし
    fill_ellipse(cx + 88, cy - 22, 6, 10, (214, 48, 49))  # 肉垂
    fill_circle(cx + 80, cy - 40, 6.4, (255, 255, 255))
    fill_circle(cx + 81, cy - 40, 3.4, (12, 12, 12))
    # 係留ロープと係員
    for dx in (-56, 0, 56):
        thick_line(cx + dx, cy + 48, cx + dx * 1.7, y + h - 12, 2.4, (230, 234, 238))
        fill_circle(cx + dx * 1.7, y + h - 16, 5, (10, 12, 16))


def caption(x, y, w, h, accent, label, sub, label_base=32, sub_base=23):
    fill_rect(x, y, w, h, (9, 11, 16))
    fill_rect(x, y, w, 5, accent)
    size = fit_size(label, w - 36, label_base, 19)
    draw_text(x + 18, y + 13, label, size, WHITE)
    if sub:
        ssize = fit_size(sub, w - 36, sub_base, 16)
        draw_text(x + 18, y + 13 + size + 9, sub, ssize, (196, 204, 214))


def panel(x, y, w, h, scene, accent, label, sub):
    scene_h = h - 86
    scene(x, y, w, scene_h)
    caption(x, y + scene_h, w, 86, accent, label, sub)
    # 枠
    fill_rect(x, y, w, 3, (52, 60, 72))
    fill_rect(x, y + h - 3, w, 3, (52, 60, 72))
    fill_rect(x, y, 3, h, (52, 60, 72))
    fill_rect(x + w - 3, y, 3, h, (52, 60, 72))


def compose():
    fill_rect(0, 0, W, H, DARKPANEL)
    # ヘッダー
    draw_text(26, 16, "THE WORLD IN ONE DAY", 50, WHITE)
    draw_text(28, 78, "THURSDAY 26 NOVEMBER 2026", 29, AMBER)
    draw_text(998, 84, "SEVEN STORIES • ONE PAGE", 21, GRAY, align="right")
    fill_rect(24, 118, W - 48, 4, AMBER)
    # リード
    lx, ly, lw, lh = 20, 130, 984, 282
    lead_scene(lx, ly, lw, lh - 100)
    caption(lx, ly + lh - 100, lw, 100, (214, 48, 49),
            "TRUMP TO PUTIN: PULL BACK",
            "MISSILES HIT KYIV AS ZELENSKYY THANKS AMERICA",
            label_base=47, sub_base=26)
    fill_rect(lx, ly, lw, 3, (52, 60, 72))
    fill_rect(lx, ly, 3, lh, (52, 60, 72))
    fill_rect(lx + lw - 3, ly, 3, lh, (52, 60, 72))
    # 4パネル(2x2)
    py, ph, pw = 424, 254, 484
    panel(20, py, pw, ph, trade_scene, (38, 150, 140),
          "US TARIFFS HIT 14 NATIONS", "NVIDIA HALTS AI CHIP SHIPMENTS")
    panel(520, py, pw, ph, korea_scene, (250, 200, 32),
          "KIM UNVEILS NUCLEAR WARHEADS", "AND SNUBS TRUMP'S TALKS")
    panel(20, py + ph + 12, pw, ph, kuwait_scene, (255, 122, 30),
          "KUWAIT DRONE STRIKE KILLS TWO", "IRAN DENIES BLAME")
    panel(520, py + ph + 12, pw, ph, parade_scene, (120, 180, 230),
          "STORM STOPS THE PARADE", "FIRST TIME IN 100 YEARS")
    # 下段: 残り2件
    by = py + 2 * ph + 24 + 14
    fill_rect(24, by - 12, W - 48, 3, (52, 60, 72))
    fill_rect(28, by + 8, 14, 14, (64, 110, 180))
    draw_text(56, by, "ECB NAMES DE COS CHIEF",
              fit_size("ECB NAMES DE COS CHIEF", 462, 27, 20), WHITE)
    fill_rect(540, by + 8, 14, 14, (92, 176, 84))
    draw_text(568, by, "HIV SHOT REACHES AFRICA",
              fit_size("HIV SHOT REACHES AFRICA", 428, 27, 20), WHITE)
    return downscale_png()


def main():
    data = compose()
    out_dir = os.environ.get("ENTRY_OUTPUT_DIR")
    if not out_dir:
        out_dir = "/output"
        try:
            os.makedirs(out_dir, exist_ok=True)
        except OSError:
            out_dir = os.path.join(os.getcwd(), "output")
            os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as f:
        f.write(data)
    print(f"wrote {path} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
