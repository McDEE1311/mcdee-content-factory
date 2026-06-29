from PIL import Image, ImageDraw, ImageFilter
import os, math

OUT = "assets/characters/master_pov"
os.makedirs(OUT, exist_ok=True)

SKIN = (244, 218, 174)
OUTLINE = (35, 32, 28)
SHADOW = (0, 0, 0, 55)

def darker(c, n=25):
    return tuple(max(0, x-n) for x in c)

def lighter(c, n=35):
    return tuple(min(255, x+n) for x in c)

def draw_shadow(d, box):
    x1,y1,x2,y2 = box
    d.ellipse([x1,y1,x2,y2], fill=SHADOW)

def draw_character(
    name,
    suit=(28, 45, 78),
    skin=SKIN,
    hair=None,
    expression="neutral",
    pose="standing",
    size=(520, 820)
):
    W,H = size
    img = Image.new("RGBA", size, (0,0,0,0))
    d = ImageDraw.Draw(img)
    cx = W//2
    draw_shadow(d, [cx-120, H-48, cx+120, H-18])
    head_r = 112
    head_cy = 155
    neck_w = 54
    neck_h = 70
    body_top = 285
    body_w = 190
    body_h = 245
    leg_h = 220
    d.rounded_rectangle(
        [cx-neck_w//2, head_cy+head_r-8, cx+neck_w//2, body_top+20],
        radius=12, fill=skin
    )
    d.ellipse(
        [cx-head_r, head_cy-head_r, cx+head_r, head_cy+head_r],
        fill=skin, outline=OUTLINE, width=5
    )
    highlight = Image.new("RGBA", size, (0,0,0,0))
    hd = ImageDraw.Draw(highlight)
    hd.ellipse(
        [cx-head_r+18, head_cy-head_r+12, cx+head_r-24, head_cy+head_r-18],
        fill=(255,255,255,28)
    )
    img.alpha_composite(highlight)
    d = ImageDraw.Draw(img)
    for side in [-1,1]:
        ex = cx + side*(head_r-4)
        d.ellipse([ex-22, head_cy-18, ex+22, head_cy+22], fill=skin, outline=OUTLINE, width=4)
        d.arc([ex-8, head_cy-7, ex+12, head_cy+12], 90, 270, fill=darker(skin,45), width=2)
    if hair:
        d.pieslice([cx-head_r+3, head_cy-head_r+4, cx+head_r-3, head_cy+55], 180, 360, fill=hair)
        d.arc([cx-head_r+3, head_cy-head_r+4, cx+head_r-3, head_cy+55], 180, 360, fill=OUTLINE, width=4)
        d.polygon([(cx-head_r+18, head_cy-45), (cx-40, head_cy-10), (cx+85, head_cy-18), (cx+head_r-14, head_cy-55)], fill=hair)
    exprs = {
        "neutral":   (0, "smile_small", 1.0),
        "happy":     (-4, "smile", 1.0),
        "confident": (-8, "smirk", 0.95),
        "serious":   (0, "flat", 0.9),
        "concerned": (10, "frown_small", 1.0),
        "angry":     (18, "frown", 0.82),
        "shocked":   (-10, "open", 1.25),
        "sad":       (10, "frown", 1.0),
    }
    brow_angle, mouth_type, eye_scale = exprs.get(expression, exprs["neutral"])
    eye_y = head_cy - 10
    eye_dx = 43
    eye_r = int(13 * eye_scale)
    for side in [-1,1]:
        ex = cx + side*eye_dx
        d.ellipse([ex-eye_r, eye_y-eye_r, ex+eye_r, eye_y+eye_r], fill=(15,15,15))
        d.ellipse([ex-4, eye_y-8, ex+2, eye_y-2], fill=(255,255,255,210))
    brow_y = eye_y - 35
    brow_len = 32
    for side in [-1,1]:
        ex = cx + side*eye_dx
        angle = brow_angle * side
        dy = int(brow_len * math.sin(math.radians(angle)))
        d.line(
            [(ex-brow_len//2, brow_y+dy//2), (ex+brow_len//2, brow_y-dy//2)],
            fill=(45,35,25), width=6
        )
    my = head_cy + 52
    mw = 44
    mc = (95, 50, 42)
    if mouth_type == "smile":
        d.arc([cx-mw, my-22, cx+mw, my+22], 15, 165, fill=mc, width=5)
    elif mouth_type == "smile_small":
        d.arc([cx-34, my-16, cx+34, my+16], 15, 165, fill=mc, width=4)
    elif mouth_type == "smirk":
        d.arc([cx-30, my-12, cx+36, my+18], 15, 150, fill=mc, width=4)
    elif mouth_type == "flat":
        d.line([cx-28, my, cx+28, my], fill=mc, width=4)
    elif mouth_type == "frown_small":
        d.arc([cx-34, my-8, cx+34, my+28], 195, 345, fill=mc, width=4)
    elif mouth_type == "frown":
        d.arc([cx-mw, my-8, cx+mw, my+30], 195, 345, fill=mc, width=5)
    elif mouth_type == "open":
        d.ellipse([cx-22, my-18, cx+22, my+24], fill=(75,34,34))
    leg_top = body_top + body_h - 4
    pant = darker(suit, 18)
    leg_w = 58
    gap = 8
    d.rounded_rectangle([cx-gap-leg_w, leg_top, cx-gap, leg_top+leg_h], radius=8, fill=pant, outline=OUTLINE, width=4)
    d.rounded_rectangle([cx+gap, leg_top, cx+gap+leg_w, leg_top+leg_h], radius=8, fill=pant, outline=OUTLINE, width=4)
    d.ellipse([cx-gap-leg_w-14, leg_top+leg_h-10, cx-gap+18, leg_top+leg_h+22], fill=(18,15,12))
    d.ellipse([cx+gap-18, leg_top+leg_h-10, cx+gap+leg_w+14, leg_top+leg_h+22], fill=(18,15,12))
    left = cx-body_w//2
    right = cx+body_w//2
    d.rounded_rectangle([left, body_top, right, body_top+body_h], radius=18, fill=suit, outline=OUTLINE, width=5)
    d.polygon([(left+8,body_top+25),(left+42,body_top+45),(left+42,body_top+body_h-20),(left+8,body_top+body_h-5)], fill=darker(suit,15))
    d.polygon([(right-8,body_top+25),(right-42,body_top+45),(right-42,body_top+body_h-20),(right-8,body_top+body_h-5)], fill=darker(suit,10))
    d.rounded_rectangle([cx-28, body_top-8, cx+28, body_top+88], radius=6, fill=(18,18,18))
    for x in range(cx-20, cx+24, 10):
        d.line([x, body_top+4, x, body_top+80], fill=(35,35,35), width=2)
    lapel = lighter(suit, 28)
    d.polygon([(cx-5, body_top+26), (left+25, body_top+10), (left+58, body_top+92)], fill=lapel, outline=OUTLINE)
    d.polygon([(cx+5, body_top+26), (right-25, body_top+10), (right-58, body_top+92)], fill=lapel, outline=OUTLINE)
    for by in [body_top+126, body_top+168]:
        d.ellipse([cx+30, by-5, cx+40, by+5], fill=darker(suit,5), outline=OUTLINE)
    arm_w = 42
    arm_len = 210
    hand_r = 25
    def default_arm(side):
        if side == -1:
            x1, x2 = left-arm_w+10, left+10
        else:
            x1, x2 = right-10, right+arm_w-10
        y1 = body_top+38
        y2 = y1+arm_len
        d.rounded_rectangle([x1,y1,x2,y2], radius=18, fill=suit, outline=OUTLINE, width=4)
        hx = (x1+x2)//2
        hy = y2+5
        d.ellipse([hx-hand_r, hy-hand_r, hx+hand_r, hy+hand_r], fill=skin, outline=OUTLINE, width=4)
    if pose == "pointing":
        default_arm(-1)
        d.rounded_rectangle([right-10, body_top+45, right+arm_w-10, body_top+155], radius=16, fill=suit, outline=OUTLINE, width=4)
        y = body_top+90
        d.rounded_rectangle([right+20, y, right+145, y+38], radius=16, fill=suit, outline=OUTLINE, width=4)
        d.ellipse([right+130, y-5, right+180, y+45], fill=skin, outline=OUTLINE, width=4)
        d.line([right+160, y+15, right+198, y+8], fill=OUTLINE, width=5)
    elif pose == "hands_up":
        for side in [-1,1]:
            x = left-35 if side == -1 else right-5
            d.rounded_rectangle([x, body_top-55, x+arm_w, body_top+115], radius=18, fill=suit, outline=OUTLINE, width=4)
            hx = x+arm_w//2
            hy = body_top-65
            d.ellipse([hx-hand_r, hy-hand_r, hx+hand_r, hy+hand_r], fill=skin, outline=OUTLINE, width=4)
    elif pose == "arms_crossed":
        default_arm(-1)
        default_arm(1)
        d.rounded_rectangle([left+18, body_top+112, right-18, body_top+154], radius=18, fill=suit, outline=OUTLINE, width=4)
    elif pose == "thinking":
        default_arm(-1)
        d.rounded_rectangle([right-10, body_top+60, right+arm_w-10, body_top+160], radius=16, fill=suit, outline=OUTLINE, width=4)
        d.rounded_rectangle([right-20, body_top+125, right+55, body_top+165], radius=16, fill=suit, outline=OUTLINE, width=4)
        d.ellipse([right+35, body_top+105, right+85, body_top+155], fill=skin, outline=OUTLINE, width=4)
    elif pose == "walking":
        default_arm(-1)
        default_arm(1)
        d.rounded_rectangle([cx-gap-leg_w-18, leg_top+18, cx-gap-18, leg_top+leg_h], radius=8, fill=pant, outline=OUTLINE, width=4)
    else:
        default_arm(-1)
        default_arm(1)
    return img

characters = [
    ("madoff_neutral",    (28,45,78), None, "neutral", "standing"),
    ("madoff_confident",  (28,45,78), None, "confident", "standing"),
    ("madoff_pointing",   (28,45,78), None, "confident", "pointing"),
    ("madoff_hands_up",   (28,45,78), None, "shocked", "hands_up"),
    ("madoff_concerned",  (28,45,78), None, "concerned", "standing"),
    ("madoff_angry",      (28,45,78), None, "angry", "standing"),
    ("madoff_crossed",    (28,45,78), None, "serious", "arms_crossed"),
    ("madoff_thinking",   (28,45,78), None, "serious", "thinking"),
    ("investor_male",     (68,68,74), (92,70,48), "happy", "standing"),
    ("investor_female",   (184,110,118), (190,190,190), "neutral", "standing"),
    ("lawyer",            (48,48,58), (75,55,40), "confident", "pointing"),
    ("judge",             (24,24,24), (165,165,160), "serious", "standing"),
    ("sec_agent",         (38,55,82), (65,50,38), "serious", "standing"),
    ("reporter",          (150,72,72), (120,70,40), "neutral", "standing"),
    ("victim",            (105,130,110), (120,90,60), "sad", "standing"),
    ("employee",          (54,82,118), (80,60,45), "concerned", "standing"),
]

for name, suit, hair, expr, pose in characters:
    img = draw_character(name, suit=suit, hair=hair, expression=expr, pose=pose)
    img.save(f"{OUT}/{name}.png")
    print("saved", name)

print("\nDone.")
