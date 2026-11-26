"""Wallpapers for apps/WallPaper/<n>.jpg (chosen in Setup > WallPaper; also behind screens without their own
background) and their thumbnails WallPaper/thumb/<n>.jpg (the picker's 232 x 165 frames).

Automotive HMI design practice (factory head units, ambient lighting, dark carbon trims, architectural facets):
- Low night luminance (L* < 14%) with deep obsidian-anthracite edges so the display never dazzles in a dark cabin
  and blends seamlessly into the dashboard bezel.
- UI-zone spatial engineering for 1024 x 600:
  * Top status bar zone (y 0..70): dark canopy for maximum contrast with #dce2e4 icons/clock and the glowing
    accent red (#f04a38) header line at y 69.
  * Center frosted-glass zone (y 94..474): smooth volumetric light folds, subtle carbon twill or brushed titanium
    micro-textures behind the translucent glass cards (alpha 26) to create genuine glassmorphic depth.
  * Bottom zone (y 480..600): anchored dark base with optional ambient horizon aligned at y 505 (below the Home
    cards and aligned pixel-for-pixel with the Radio bottom bar).
- True 32-bit floating-point (float32) light transport + Triangular PDF (TPDF) sub-pixel dithering before 8-bit
  quantization, completely eliminating Mach colour banding on dark gradients.

usage: wallpapers.py <out WallPaper dir> [preview.png] [--all]
"""
import array
import math
import os
import sys
from PIL import Image, ImageDraw, ImageFilter, ImageMath

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../tools'))

W, H = 1024, 600
THUMB = (228, 161)            # inside the 232 x 165 frames of the picker


def float_field(base_top, base_bottom, lights, vig=0.45, angle=0.0, gw=256, gh=150):
    """Compute smooth studio light field in 32-bit float on (gw x gh) and bicubic-upscale in float32 to (W x H)."""
    ca, sa = math.cos(angle), math.sin(angle)
    aspect = W / H
    buf_r = array.array('f', [0.0] * (gw * gh))
    buf_g = array.array('f', [0.0] * (gw * gh))
    buf_b = array.array('f', [0.0] * (gw * gh))

    idx = 0
    for j in range(gh):
        y = (j + 0.5) / gh
        dy_v = (y - 0.5) * 1.3
        for i in range(gw):
            x = (i + 0.5) / gw
            t = min(1.0, max(0.0, (x - 0.5) * sa + (y - 0.5) * ca + 0.5))
            ts = t * t * (3.0 - 2.0 * t)
            r = base_top[0] * (1.0 - ts) + base_bottom[0] * ts
            g = base_top[1] * (1.0 - ts) + base_bottom[1] * ts
            b = base_top[2] * (1.0 - ts) + base_bottom[2] * ts

            for lspec in lights:
                (lx, ly), rad, col, strength = lspec[:4]
                sx, sy, rot = lspec[4] if len(lspec) > 4 else (1.0, 1.0, 0.0)
                dx = (x - lx) * aspect
                dy = y - ly
                if rot:
                    cr, sr = math.cos(rot), math.sin(rot)
                    dx, dy = dx * cr + dy * sr, -dx * sr + dy * cr
                dx /= sx
                dy /= sy
                w = strength * math.exp(-(dx * dx + dy * dy) / (2.0 * rad * rad))
                r = r * (1.0 - w) + col[0] * w
                g = g * (1.0 - w) + col[1] * w
                b = b * (1.0 - w) + col[2] * w

            dx_v = (x - 0.5) * 1.1
            v = 1.0 - vig * (min(1.0, (dx_v * dx_v + dy_v * dy_v) * 2.2) ** 1.4)
            buf_r[idx] = r * v
            buf_g[idx] = g * v
            buf_b[idx] = b * v
            idx += 1

    return [
        Image.frombytes('F', (gw, gh), buf.tobytes()).resize((W, H), Image.BICUBIC)
        for buf in (buf_r, buf_g, buf_b)
    ]


def add_float_layer(channels, layer_rgb, strength=1.0, blur=0):
    """Add an RGB light layer into the 32-bit float channels."""
    if blur > 0:
        layer_rgb = layer_rgb.filter(ImageFilter.GaussianBlur(blur))
    lr, lg, lb = layer_rgb.split()
    return [
        ImageMath.lambda_eval(lambda d: d['c'] + d['l'] * strength, c=ch_f, l=l_c.convert('F'))
        for ch_f, l_c in zip(channels, (lr, lg, lb))
    ]


def radial_mask_f(vig=0.65):
    """Smooth radial vignette mask in 32-bit float (1.0 in centre, 1.0 - vig at corners)."""
    gw, gh = 128, 75
    buf = array.array('f', [0.0] * (gw * gh))
    idx = 0
    for j in range(gh):
        dy = ((j + 0.5) / gh - 0.5) * 1.65
        for i in range(gw):
            dx = ((i + 0.5) / gw - 0.5) * 1.55
            d2 = min(1.0, dx * dx + dy * dy)
            buf[idx] = 1.0 - vig * (d2 ** 1.2)
            idx += 1
    return Image.frombytes('F', (gw, gh), buf.tobytes()).resize((W, H), Image.BICUBIC)


def finalize_float(channels, dither=1.35):
    """Quantize 32-bit float RGB channels to 8-bit using Triangular PDF (TPDF) sub-pixel dithering."""
    n_lum1 = Image.effect_noise((W, H), 32).convert('F')
    n_lum2 = Image.effect_noise((W, H), 32).convert('F')
    scale = dither / 64.0
    out_ch = []
    for ch_f in channels:
        nc = Image.effect_noise((W, H), 16).convert('F')
        q = ImageMath.lambda_eval(
            lambda d: min(255.0, max(0.0, d['c'] + (d['n1'] + d['n2'] - 256.0) * scale + (d['nc'] - 128.0) * (scale * 0.25))),
            c=ch_f, n1=n_lum1, n2=n_lum2, nc=nc
        ).convert('L')
        out_ch.append(q)
    return Image.merge('RGB', out_ch)


# --- wallpapers in the UI's palette (accent red #f04a38 + frosted titanium #c8e1e4 / #dce2e4) ---

def silk_wave():
    """0: Silk Wave - soft 3D satin folds in crimson & cool titanium."""
    ch = float_field(
        (9, 12, 16), (4, 5, 7),
        [
            ((0.15, 0.14), 0.48, (36, 50, 60), 0.65, (1.35, 0.9, -0.25)),
            ((0.85, 0.86), 0.50, (118, 24, 18), 0.72, (1.35, 0.9, -0.25)),
            ((0.48, 0.50), 0.42, (42, 16, 20), 0.36, (1.5, 0.75, -0.35)),
        ],
        vig=0.46, angle=0.35
    )
    gw, gh = 512, 300
    sr = array.array('f', [0.0] * (gw * gh))
    sg = array.array('f', [0.0] * (gw * gh))
    sb = array.array('f', [0.0] * (gw * gh))

    idx = 0
    for j in range(gh):
        y = (j + 0.5) / gh
        for i in range(gw):
            x = (i + 0.5) / gw
            xfade = math.sin(min(1.0, max(0.0, x)) * math.pi) ** 0.8

            # Primary warm crimson satin fold
            y1 = 0.68 - 0.16 * x + 0.075 * math.sin(x * math.pi * 2.0 - 0.35)
            d1 = y - y1
            if d1 >= -0.03:
                u1 = max(0.0, d1 + 0.03)
                sheet1 = math.exp(-u1 / 0.11) * (1.0 - math.exp(-u1 / 0.018))
            else:
                sheet1 = 0.0
            rim1 = math.exp(-((d1 / 0.022) ** 2))
            w1_s, w1_r = sheet1 * xfade, rim1 * xfade

            # Secondary cool titanium-slate upper counter-fold
            y2 = 0.32 + 0.14 * x - 0.065 * math.sin(x * math.pi * 1.85 + 0.45)
            d2 = y2 - y
            if d2 >= -0.03:
                u2 = max(0.0, d2 + 0.03)
                sheet2 = math.exp(-u2 / 0.10) * (1.0 - math.exp(-u2 / 0.018))
            else:
                sheet2 = 0.0
            rim2 = math.exp(-((d2 / 0.022) ** 2))
            w2_s, w2_r = sheet2 * xfade, rim2 * xfade

            sr[idx] = w1_s * 54.0 + w1_r * 58.0 + w2_s * 16.0 + w2_r * 26.0
            sg[idx] = w1_s * 11.0 + w1_r * 14.0 + w2_s * 24.0 + w2_r * 36.0
            sb[idx] = w1_s * 10.0 + w1_r * 12.0 + w2_s * 30.0 + w2_r * 42.0
            idx += 1

    for k, buf in enumerate((sr, sg, sb)):
        wf = Image.frombytes('F', (gw, gh), buf.tobytes()).resize((W, H), Image.BICUBIC)
        ch[k] = ImageMath.lambda_eval(lambda d: d['c'] + d['w'], c=ch[k], w=wf)
    return finalize_float(ch, dither=1.35)


def ambient_horizon():
    """1: Ambient Horizon - ambient light blade aligned at y=505 + satin floor reflection."""
    ch = float_field(
        (10, 12, 15), (4, 4, 6),
        [
            ((0.50, -0.08), 0.52, (38, 46, 54), 0.56, (1.6, 0.8, 0.0)),
            ((0.50, 0.90), 0.38, (112, 22, 16), 0.68, (1.8, 0.55, 0.0)),
            ((0.50, 1.08), 0.45, (48, 10, 8), 0.50, (2.0, 0.6, 0.0)),
        ],
        vig=0.42
    )
    y_line = 505
    bloom = Image.new('RGB', (W, H), (0, 0, 0))
    core = Image.new('RGB', (W, H), (0, 0, 0))
    ImageDraw.Draw(bloom).line([(-20, y_line), (W + 20, y_line)], fill=(185, 38, 28), width=6)
    ImageDraw.Draw(core).line([(-20, y_line), (W + 20, y_line)], fill=(240, 74, 56), width=2)

    fade = Image.new('L', (W, 1))
    for x in range(W):
        fade.putpixel((x, 0), round(255 * math.exp(-((x - W / 2) / (W * 0.36)) ** 2)))
    fade_full = fade.resize((W, H))
    bloom = Image.composite(bloom, Image.new('RGB', (W, H)), fade_full)
    core = Image.composite(core, Image.new('RGB', (W, H)), fade_full)

    ch = add_float_layer(ch, bloom, strength=0.80, blur=20)
    ch = add_float_layer(ch, bloom, strength=0.40, blur=6)
    ch = add_float_layer(ch, core, strength=0.48, blur=1.5)
    return finalize_float(ch, dither=1.3)


def carbon_crimson():
    """2: Carbon & Crimson - dark carbon twill with indirect crimson & brushed steel rim lighting."""
    ch = float_field(
        (12, 14, 17), (5, 6, 8),
        [
            ((0.12, 0.88), 0.46, (122, 24, 18), 0.72, (1.2, 0.95, -0.2)),
            ((0.88, 0.12), 0.48, (42, 52, 60), 0.60, (1.2, 0.95, -0.2)),
        ],
        vig=0.48, angle=0.4
    )
    pat = Image.new('L', (6, 6))
    for y in range(6):
        for x in range(6):
            phase = (x + y) % 6
            v = 156 if phase < 2 else (128 if phase < 4 else 100)
            if (x % 3 == 0) ^ (y % 3 == 0):
                v += 8
            pat.putpixel((x, y), v)
    weave = Image.new('L', (W, H))
    for y in range(0, H, 6):
        for x in range(0, W, 6):
            weave.paste(pat, (x, y))
    weave_f = weave.convert('F')
    mask_f = radial_mask_f(vig=0.88)
    ch = [
        ImageMath.lambda_eval(
            lambda d: d['c'] + (d['w'] - 128.0) * (0.11 * d['m'] * min(1.0, d['c'] / 28.0)),
            c=c, w=weave_f, m=mask_f
        )
        for c in ch
    ]
    return finalize_float(ch, dither=1.3)


def titanium_facets():
    """3: Titanium & Ruby - soft-beveled architectural body-line creases."""
    ch = float_field(
        (10, 12, 15), (4, 5, 7),
        [
            ((0.20, 0.80), 0.46, (116, 24, 18), 0.66, (1.4, 0.8, -0.4)),
            ((0.80, 0.20), 0.46, (44, 54, 62), 0.60, (1.4, 0.8, -0.4)),
        ],
        vig=0.46, angle=0.4
    )
    gw, gh = 512, 300
    sr = array.array('f', [0.0] * (gw * gh))
    sg = array.array('f', [0.0] * (gw * gh))
    sb = array.array('f', [0.0] * (gw * gh))

    idx = 0
    for j in range(gh):
        y = (j + 0.5) / gh
        for i in range(gw):
            x = (i + 0.5) / gw
            xfade = math.sin(min(1.0, max(0.0, x)) * math.pi) ** 0.85

            c1_y = 0.82 - 0.54 * (x ** 0.90)
            d1 = y - c1_y
            bevel1 = math.exp(-max(0.0, d1) / 0.13) * (1.0 if d1 >= 0 else math.exp(-((-d1) / 0.015) ** 2))
            edge1 = math.exp(-((d1 / 0.018) ** 2))

            c2_y = 0.54 - 0.40 * (x ** 1.04)
            d2 = c2_y - y
            bevel2 = math.exp(-max(0.0, d2) / 0.11) * (1.0 if d2 >= 0 else math.exp(-((-d2) / 0.015) ** 2))
            edge2 = math.exp(-((d2 / 0.018) ** 2))

            sr[idx] = xfade * (bevel1 * 34.0 + edge1 * 52.0 + bevel2 * 12.0 + edge2 * 24.0)
            sg[idx] = xfade * (bevel1 * 7.0  + edge1 * 13.0 + bevel2 * 16.0 + edge2 * 30.0)
            sb[idx] = xfade * (bevel1 * 6.0  + edge1 * 11.0 + bevel2 * 20.0 + edge2 * 36.0)
            idx += 1

    for k, buf in enumerate((sr, sg, sb)):
        wf = Image.frombytes('F', (gw, gh), buf.tobytes()).resize((W, H), Image.BICUBIC)
        ch[k] = ImageMath.lambda_eval(lambda d: d['c'] + d['w'], c=ch[k], w=wf)
    return finalize_float(ch, dither=1.35)


def honeycomb():
    """4: Honeycomb Vignette - subtle hexagonal micro-grille lit by crimson & gunmetal."""
    ch = float_field(
        (9, 10, 12), (4, 4, 5),
        [
            ((0.80, 0.82), 0.44, (130, 24, 18), 0.75, (1.2, 0.9, -0.25)),
            ((0.18, 0.18), 0.46, (38, 46, 54), 0.58, (1.2, 0.9, -0.25)),
        ],
        vig=0.48
    )
    ss = 2
    sw, sh = W * ss, H * ss
    hex_im = Image.new('L', (sw, sh), 0)
    d = ImageDraw.Draw(hex_im)
    r = 16 * ss
    dx = r * math.sqrt(3)
    dy = r * 1.5
    for row in range(-1, int(sh / dy) + 3):
        cy = row * dy
        for col in range(-1, int(sw / dx) + 3):
            cx = col * dx + (dx / 2 if row % 2 else 0)
            pts = [
                (cx + (r - 1.5 * ss) * math.cos(math.radians(60 * k + 30)),
                 cy + (r - 1.5 * ss) * math.sin(math.radians(60 * k + 30)))
                for k in range(6)
            ]
            d.polygon(pts, outline=180, width=ss)
    hex_im = hex_im.resize((W, H), Image.LANCZOS).convert('F')
    mask_f = radial_mask_f(vig=0.92)
    ch = [
        ImageMath.lambda_eval(
            lambda d: d['c'] + (d['h'] / 255.0) * d['m'] * (0.22 * d['c']),
            c=c, h=hex_im, m=mask_f
        )
        for c in ch
    ]
    return finalize_float(ch, dither=1.35)


def studio_glow():
    """5: Studio Dual-Glow - zero-banding 32-bit float studio light in crimson & slate."""
    ch = float_field(
        (14, 11, 12), (5, 5, 6),
        [
            ((0.10, 0.08), 0.46, (124, 24, 18), 0.76, (1.15, 0.95, -0.2)),
            ((0.90, 0.92), 0.44, (88, 20, 18), 0.62, (1.15, 0.95, -0.2)),
            ((0.82, 0.14), 0.42, (34, 42, 50), 0.48, (1.1, 1.0, 0.0)),
        ],
        vig=0.42, angle=0.35
    )
    return finalize_float(ch, dither=1.45)


def brushed_titanium():
    """6: Highline Dark Brushed Titanium — horizontal brushed metal + subtle red ambient underglow."""
    ch = float_field(
        (22, 25, 29), (6, 7, 9),
        [
            ((0.48, -0.10), 0.56, (72, 82, 92), 0.52, (1.7, 0.75, 0.0)),
            ((0.52, 1.12), 0.42, (98, 20, 16), 0.58, (1.6, 0.65, 0.0)),
        ],
        vig=0.48, angle=0.15
    )
    raw_noise = Image.effect_noise((W // 8, H), 48).resize((W, H), Image.BICUBIC)
    raw_noise = raw_noise.filter(ImageFilter.GaussianBlur((8, 0.5))).convert('F')
    mask_f = radial_mask_f(vig=0.65)
    ch = [
        ImageMath.lambda_eval(
            lambda d: d['c'] + (d['n'] - 128.0) * 0.075 * d['m'],
            c=c, n=raw_noise, m=mask_f
        )
        for c in ch
    ]
    return finalize_float(ch, dither=1.25)


def pure_night():
    """7: Pure Night - deep obsidian minimal night mode with soft ruby-graphite core."""
    ch = float_field(
        (8, 9, 11), (3, 3, 4),
        [
            ((0.50, 0.58), 0.40, (32, 38, 44), 0.48, (1.4, 0.85, 0.0)),
            ((0.50, 1.12), 0.42, (96, 18, 14), 0.65, (1.6, 0.65, 0.0)),
        ],
        vig=0.38
    )
    return finalize_float(ch, dither=1.35)


ALL_OEM = [
    ('Silk Wave', silk_wave),
    ('Ambient Horizon', ambient_horizon),
    ('Carbon & Crimson', carbon_crimson),
    ('Titanium & Ruby', titanium_facets),
    ('Honeycomb Vignette', honeycomb),
    ('Studio Dual-Glow', studio_glow),
    ('Brushed Titanium', brushed_titanium),
    ('Pure Night', pure_night),
]

# Top 4 active in the navigation's 2x2 Setup > WallPaper picker (2, 4, 7, 1 from ALL_OEM)
COMBINED = [ALL_OEM[2], ALL_OEM[4], ALL_OEM[7], ALL_OEM[1]]


def generate(out_dir, pictures=None):
    os.makedirs(os.path.join(out_dir, 'thumb'), exist_ok=True)
    made = []
    for n, (name, fn) in enumerate(pictures or COMBINED):
        im = fn()
        im.save(os.path.join(out_dir, f'{n}.jpg'), 'JPEG', quality=96, subsampling=0)
        im.resize(THUMB, Image.LANCZOS).save(
            os.path.join(out_dir, 'thumb', f'{n}.jpg'), 'JPEG', quality=94, subsampling=0
        )
        made.append((name, im))
    return made


def preview(made, path):
    tw, th = 340, 200
    rows = (len(made) + 3) // 4
    sheet = Image.new('RGB', (tw * 4 + 50, (th + 34) * rows + 14), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    for k, (name, im) in enumerate(made):
        x, y = 10 + (k % 4) * (tw + 10), 10 + (k // 4) * (th + 34)
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (x, y))
        d.text((x, y + th + 6), f'{k}: {name}', fill=(220, 226, 228))
    sheet.save(path)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--all']
    use_all = '--all' in sys.argv[1:]
    made = generate(args[0], ALL_OEM if use_all else COMBINED)
    if len(args) > 1:
        preview(made, args[1])
    print(f'{args[0]}: {len(made)} wallpapers')
