"""
Master POV Character Renderer V2
Matches the reference style: big round head, large eyes, clean body, thick outlines.
"""
from PIL import Image, ImageDraw
import math, os

def draw_character(
    pose="standing",
    expression="neutral", 
    suit_color=(25, 50, 95),
    skin_color=(230, 195, 155),
    hair_color=(60, 40, 25),
    hair_style="short",  # short, grey, none
    size=(380, 680),
    outline_w=4,
):
    W, H = size
    img = Image.new("RGBA", (W, H), (0,0,0,0))
    d = ImageDraw.Draw(img)
    OC = (30, 25, 20)
    OW = outline_w

    def ell(x0,y0,x1,y1,fill,oc=None,ow=None):
        d.ellipse([x0,y0,x1,y1], fill=fill, outline=oc or OC, width=ow or OW)
    def rec(x0,y0,x1,y1,fill,oc=None,ow=None):
        d.rectangle([x0,y0,x1,y1], fill=fill, outline=oc or OC, width=ow or OW)
    def pol(pts, fill, oc=None):
        d.polygon(pts, fill=fill, outline=oc or OC)

    cx = W // 2

    # ── HEAD (big, round, 38% of height) ──────────────
    HEAD_R = int(H * 0.190)
    HEAD_CY = int(H * 0.210)

    # Head
    ell(cx-HEAD_R, HEAD_CY-HEAD_R, cx+HEAD_R, HEAD_CY+HEAD_R, skin_color)

    # Hair
    if hair_style == "short" and hair_color:
        # Flat cap on top
        hair_h = int(HEAD_R * 0.52)
        d.pieslice([cx-HEAD_R, HEAD_CY-HEAD_R, cx+HEAD_R, HEAD_CY+HEAD_R],
                   start=190, end=350, fill=hair_color)
        d.rectangle([cx-HEAD_R, HEAD_CY-HEAD_R, cx+HEAD_R, HEAD_CY-HEAD_R+hair_h],
                    fill=hair_color)
        # Re-draw head circle top to clean up
        d.arc([cx-HEAD_R, HEAD_CY-HEAD_R, cx+HEAD_R, HEAD_CY+HEAD_R],
              start=190, end=350, fill=OC, width=OW)
    elif hair_style == "grey" and hair_color:
        hair_h = int(HEAD_R * 0.45)
        d.pieslice([cx-HEAD_R+2, HEAD_CY-HEAD_R+2, cx+HEAD_R-2, HEAD_CY+int(HEAD_R*0.1)],
                   start=180, end=360, fill=hair_color)

    # Head outline
    d.ellipse([cx-HEAD_R, HEAD_CY-HEAD_R, cx+HEAD_R, HEAD_CY+HEAD_R],
              outline=OC, width=OW)

    # Ears
    ER = int(HEAD_R * 0.195)
    for ex in [-1, 1]:
        ell(cx+ex*HEAD_R-ER, HEAD_CY-ER//2,
            cx+ex*HEAD_R+ER, HEAD_CY+ER//2, skin_color)

    # ── EYES (large, expressive) ───────────────────────
    EYE_Y = HEAD_CY - int(HEAD_R * 0.05)
    EYE_OFF = int(HEAD_R * 0.42)
    EYE_R = int(HEAD_R * 0.185)

    exp_eye = {"shocked": 1.30, "angry": 0.75, "serious": 0.80}.get(expression, 1.0)
    for ex in [-EYE_OFF, EYE_OFF]:
        er = int(EYE_R * exp_eye)
        ecx = cx + ex
        ell(ecx-er, EYE_Y-er, ecx+er, EYE_Y+er, (22,22,22), oc=(22,22,22))
        d.ellipse([ecx-er//3, EYE_Y-int(er*0.6), ecx, EYE_Y-int(er*0.1)],
                  fill=(255,255,255,220))

    # ── EYEBROWS ──────────────────────────────────────
    BW_Y = EYE_Y - int(HEAD_R * 0.285)
    BW_L = int(HEAD_R * 0.38)
    BW_W = max(4, int(HEAD_R * 0.10))
    angles = {"neutral":0,"happy":-5,"confident":-4,"concerned":10,
              "angry":18,"serious":8,"shocked":-10,"sad":12,"smug":-8}
    angle = angles.get(expression, 0)
    for ex in [-EYE_OFF, EYE_OFF]:
        bx = cx + ex
        s = 1 if ex > 0 else -1
        dy = int(BW_L * math.sin(math.radians(angle*s)))
        d.line([(bx-BW_L//2, BW_Y+dy//2),(bx+BW_L//2, BW_Y-dy//2)],
               fill=(55,38,22), width=BW_W)

    # ── MOUTH ─────────────────────────────────────────
    MY = HEAD_CY + int(HEAD_R * 0.40)
    MW = int(HEAD_R * 0.44)
    MC = (100, 58, 42)
    MH = max(2, int(HEAD_R * 0.075))
    mouths = {"happy":(12,168),"confident":(10,170),"neutral":(5,175),
              "serious":(0,180),"smug":(5,130),"concerned":(192,348),
              "sad":(195,345),"angry":(200,340)}
    if expression == "shocked":
        ell(cx-MW//2, MY-MW//3, cx+MW//2, MY+MW//3, (65,30,30))
    else:
        arc = mouths.get(expression, (5,175))
        if arc[0] < 180:
            d.arc([cx-MW, MY-MW//3, cx+MW, MY+MW//3],
                  start=arc[0], end=arc[1], fill=MC, width=MH)
        else:
            d.arc([cx-MW, MY-MW//3, cx+MW, MY+MW//3],
                  start=arc[0], end=arc[1], fill=MC, width=MH)

    # ── NECK ──────────────────────────────────────────
    NW = int(HEAD_R * 0.46)
    NY = HEAD_CY + HEAD_R - 5
    NH = int(H * 0.055)
    rec(cx-NW//2, NY, cx+NW//2, NY+NH, skin_color, oc=skin_color)

    # ── BODY (wider, cleaner) ──────────────────────────
    BT = NY + NH - 4
    BW = int(W * 0.52)
    BH = int(H * 0.285)
    BL = cx - BW//2
    BR = cx + BW//2

    # Turtleneck
    TNW = NW + 6
    rec(cx-TNW//2, BT, cx+TNW//2, BT+int(BH*0.16), (18,18,18))

    # Jacket
    rec(BL, BT, BR, BT+BH, suit_color)

    # Shirt strip
    SW = int(BW * 0.14)
    rec(cx-SW//2, BT, cx+SW//2, BT+BH, (215,215,215), oc=(185,185,185), ow=1)
    rec(cx-TNW//2, BT, cx+TNW//2, BT+int(BH*0.16), (18,18,18), oc=(18,18,18))

    # Lapels
    LC = tuple(min(255,c+30) for c in suit_color)
    pol([(cx,BT+int(BH*0.10)),(BL+int(BW*0.10),BT+int(BH*0.02)),
         (BL+int(BW*0.24),BT+int(BH*0.40))], LC)
    pol([(cx,BT+int(BH*0.10)),(BR-int(BW*0.10),BT+int(BH*0.02)),
         (BR-int(BW*0.24),BT+int(BH*0.40))], LC)
    d.rectangle([BL,BT,BR,BT+BH], outline=OC, width=OW)

    # Button
    d.ellipse([cx-5,BT+int(BH*0.52)-5,cx+5,BT+int(BH*0.52)+5], fill=LC, outline=OC, width=1)

    # ── ARMS ──────────────────────────────────────────
    AW = int(W * 0.105)
    AH = int(H * 0.245)
    AT = BT + int(BH * 0.05)
    HR = int(AW * 0.75)
    SC = suit_color

    def arm_left_normal():
        rec(BL-AW+5, AT, BL+5, AT+AH, SC)
        ell(BL-AW//2-HR+5, AT+AH-HR, BL-AW//2+HR+5, AT+AH+HR, skin_color)
    def arm_right_normal():
        rec(BR-5, AT, BR+AW-5, AT+AH, SC)
        ell(BR+AW//2-HR-5, AT+AH-HR, BR+AW//2+HR-5, AT+AH+HR, skin_color)

    if pose == "pointing":
        arm_left_normal()
        rec(BR-5, AT, BR+AW-5, AT+int(AH*0.52), SC)
        FAY = AT + int(AH*0.42)
        rec(BR+AW-14, FAY, BR+AW+int(AH*0.52), FAY+AW, SC)
        ell(BR+AW+int(AH*0.42)-HR, FAY+AW//2-HR,
            BR+AW+int(AH*0.42)+HR, FAY+AW//2+HR, skin_color)

    elif pose == "hands_up":
        RAISE = int(AH * 0.58)
        rec(BL-AW+5, AT-RAISE, BL+5, AT+AH-RAISE, SC)
        ell(BL-AW//2-HR+5, AT-RAISE-HR, BL-AW//2+HR+5, AT-RAISE+HR, skin_color)
        rec(BR-5, AT-RAISE, BR+AW-5, AT+AH-RAISE, SC)
        ell(BR+AW//2-HR-5, AT-RAISE-HR, BR+AW//2+HR-5, AT-RAISE+HR, skin_color)

    elif pose == "arms_crossed":
        arm_left_normal()
        arm_right_normal()
        rec(BL+12, AT+int(AH*0.32), BR-12, AT+int(AH*0.58), SC)
        d.rectangle([BL+12,AT+int(AH*0.32),BR-12,AT+int(AH*0.58)], outline=OC, width=OW)

    elif pose == "talking":
        arm_left_normal()
        rec(BR-5, AT, BR+AW-5, AT+int(AH*0.62), SC)
        ell(BR+AW//2-HR-5, AT+int(AH*0.52)-HR,
            BR+AW//2+HR-5, AT+int(AH*0.52)+HR, skin_color)

    elif pose == "walking":
        # Slight offset for walking look
        rec(BL-AW+5, AT, BL+5, AT+int(AH*0.85), SC)
        ell(BL-AW//2-HR+5, AT+int(AH*0.75)-HR,
            BL-AW//2+HR+5, AT+int(AH*0.75)+HR, skin_color)
        rec(BR-5, AT+int(AH*0.15), BR+AW-5, AT+AH, SC)
        ell(BR+AW//2-HR-5, AT+AH-HR, BR+AW//2+HR-5, AT+AH+HR, skin_color)
    else:
        arm_left_normal()
        arm_right_normal()

    # ── LEGS ──────────────────────────────────────────
    LT = BT + BH
    LW2 = int(BW * 0.385)
    LH = int(H * 0.295)
    LC2 = tuple(max(0,c-20) for c in suit_color)
    GAP = int(BW * 0.048)

    if pose == "walking":
        # Offset legs for walking
        rec(cx-GAP-LW2, LT, cx-GAP, LT+int(LH*0.85), LC2)
        rec(cx+GAP, LT+int(LH*0.18), cx+GAP+LW2, LT+LH, LC2)
        for lx,ly in [(cx-GAP-LW2, LT+int(LH*0.78)),(cx+GAP, LT+LH-8)]:
            d.ellipse([lx-6,ly,lx+LW2+10,ly+20], fill=(20,15,12), outline=(10,8,6), width=1)
    else:
        rec(cx-GAP-LW2, LT, cx-GAP, LT+LH, LC2)
        rec(cx+GAP, LT, cx+GAP+LW2, LT+LH, LC2)
        for lx in [cx-GAP-LW2, cx+GAP]:
            d.ellipse([lx-6,LT+LH-8,lx+LW2+10,LT+LH+20],
                      fill=(20,15,12), outline=(10,8,6), width=1)

    return img


CHARACTERS = {
    # Madoff — grey hair, navy suit
    "madoff_standing":     dict(suit_color=(25,48,88), hair_color=(150,148,145), hair_style="grey", expression="confident",  pose="standing"),
    "madoff_pointing":     dict(suit_color=(25,48,88), hair_color=(150,148,145), hair_style="grey", expression="confident",  pose="pointing"),
    "madoff_hands_up":     dict(suit_color=(25,48,88), hair_color=(150,148,145), hair_style="grey", expression="shocked",    pose="hands_up"),
    "madoff_concerned":    dict(suit_color=(25,48,88), hair_color=(150,148,145), hair_style="grey", expression="concerned",  pose="standing"),
    "madoff_angry":        dict(suit_color=(25,48,88), hair_color=(150,148,145), hair_style="grey", expression="angry",      pose="standing"),
    "madoff_talking":      dict(suit_color=(25,48,88), hair_color=(150,148,145), hair_style="grey", expression="confident",  pose="talking"),
    "madoff_arms_crossed": dict(suit_color=(25,48,88), hair_color=(150,148,145), hair_style="grey", expression="serious",    pose="arms_crossed"),
    "madoff_walking":      dict(suit_color=(25,48,88), hair_color=(150,148,145), hair_style="grey", expression="neutral",    pose="walking"),
    # Supporting cast
    "investor_male":       dict(suit_color=(62,62,68), hair_color=(75,52,32),   hair_style="short", expression="happy",     pose="standing"),
    "investor_female":     dict(suit_color=(105,72,92),hair_color=(48,32,22),   hair_style="short", expression="confident", pose="standing"),
    "judge":               dict(suit_color=(12,12,12), hair_color=(138,128,118),hair_style="grey",  expression="serious",   pose="standing"),
    "sec_agent":           dict(suit_color=(28,48,88), hair_color=(52,38,22),   hair_style="short", expression="serious",   pose="standing"),
    "lawyer":              dict(suit_color=(42,28,28), hair_color=(58,42,28),   hair_style="short", expression="confident", pose="pointing"),
    "reporter":            dict(suit_color=(135,52,52),hair_color=(52,32,22),   hair_style="short", expression="neutral",   pose="talking"),
    "victim":              dict(suit_color=(82,102,82),hair_color=(88,68,48),   hair_style="short", expression="sad",       pose="standing"),
    "employee":            dict(suit_color=(48,72,108),hair_color=(58,42,28),   hair_style="short", expression="concerned", pose="standing"),
}

if __name__ == "__main__":
    import sys
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "assets/characters/vector"
    os.makedirs(out_dir, exist_ok=True)
    print(f"Generating {len(CHARACTERS)} characters...")
    for name, cfg in CHARACTERS.items():
        img = draw_character(**cfg, size=(380,680))
        out = f"{out_dir}/{name}.png"
        img.save(out)
        print(f"  {name}")
    print(f"Done → {out_dir}")
