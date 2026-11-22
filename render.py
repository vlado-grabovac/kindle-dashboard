"""Generise dashboard.png (758x1024, 16 nijansi sive) za Kindle Paperwhite 2."""
import datetime as dt
import json
import math
import os
import sys
import traceback
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

W, H = 758, 1024
LAT, LON = 43.8563, 18.4131
CITY = "Sarajevo"
TZ = ZoneInfo("Europe/Sarajevo")
OUT_DIR = os.environ.get("OUT_DIR", "site")
HERE = os.path.dirname(os.path.abspath(__file__))

DID = os.environ.get("XIAOMI_DID", "749431548")
# MIoT mapiranje za Xiaomi Smart Air Purifier 4 Pro (zhimi.airp.vb4).
# Ako se pokaze drugacije, promijeni preko env varijable PURIFIER_MAP (JSON).
PMAP = {
    "power": [2, 1],
    "mode": [2, 4],
    "humidity": [3, 1],
    "pm25": [3, 4],
    "temperature": [3, 7],
    "filter": [4, 1],
}
if os.environ.get("PURIFIER_MAP"):
    PMAP.update(json.loads(os.environ["PURIFIER_MAP"]))
MODES = {0: "auto", 1: "noćni", 2: "favorit", 3: "ručni"}

DANI = ["Ponedjeljak", "Utorak", "Srijeda", "Četvrtak", "Petak", "Subota", "Nedjelja"]
DANI_K = ["Pon", "Uto", "Sri", "Čet", "Pet", "Sub", "Ned"]
MJESECI = ["januar", "februar", "mart", "april", "maj", "juni", "juli",
           "august", "septembar", "oktobar", "novembar", "decembar"]


def font(weight, size):
    name = {"r": "Inter-Regular.otf", "m": "Inter-Medium.otf", "b": "Inter-SemiBold.otf"}[weight]
    return ImageFont.truetype(os.path.join(HERE, "fonts", name), size)


# ---------------------------------------------------------------- podaci
def get_weather():
    r = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": LAT, "longitude": LON, "timezone": "Europe/Sarajevo",
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset",
        "forecast_days": 4,
    }, timeout=20)
    r.raise_for_status()
    return r.json()


def get_air():
    r = requests.get("https://air-quality-api.open-meteo.com/v1/air-quality", params={
        "latitude": LAT, "longitude": LON, "timezone": "Europe/Sarajevo",
        "current": "pm2_5,pm10,european_aqi",
    }, timeout=20)
    r.raise_for_status()
    return r.json()


def get_purifier():
    user, pw = os.environ.get("XIAOMI_USER"), os.environ.get("XIAOMI_PASS")
    pt, uid = os.environ.get("XIAOMI_PASSTOKEN"), os.environ.get("XIAOMI_USERID")
    if not (pt and uid) and not (user and pw):
        print("[xiaomi] nema XIAOMI_USER/XIAOMI_PASS, preskacem")
        return None
    from xiaomi import XiaomiCloud
    cloud = XiaomiCloud(user, pw, token_file=os.environ.get("TOKEN_FILE", ".xiaomi_token.json"),
                        pass_token=pt, user_id=uid,
                        device_id=os.environ.get("XIAOMI_DEVICEID") or None)
    # citamo sire podrucje (debug u logu), pa mapiramo
    pairs = [(2, p) for p in range(1, 7)] + [(3, p) for p in range(1, 13)] + [(4, p) for p in range(1, 6)]
    vals, srv = cloud.get_props(DID, pairs, server=os.environ.get("XIAOMI_SERVER") or None)
    print("[xiaomi] sirove vrijednosti:", {f"{s}.{p}": v for (s, p), v in sorted(vals.items())})
    return {k: vals.get(tuple(v)) for k, v in PMAP.items()}


def safe(fn, label):
    try:
        return fn()
    except Exception as e:
        print(f"[{label}] GREŠKA: {e}")
        traceback.print_exc()
        return None


# ---------------------------------------------------------------- ikone
def wmo_kind(code):
    if code is None:
        return "?"
    if code == 0:
        return "sun"
    if code in (1, 2):
        return "partly"
    if code == 3:
        return "cloud"
    if code in (45, 48):
        return "fog"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code >= 95:
        return "storm"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    return "cloud"


def wmo_text(code):
    t = {0: "vedro", 1: "pretežno vedro", 2: "djelimično oblačno", 3: "oblačno",
         45: "magla", 48: "magla s injem", 51: "rosulja", 53: "rosulja", 55: "jaka rosulja",
         56: "ledena rosulja", 57: "ledena rosulja", 61: "slaba kiša", 63: "kiša", 65: "jaka kiša",
         66: "ledena kiša", 67: "ledena kiša", 71: "slab snijeg", 73: "snijeg", 75: "jak snijeg",
         77: "sitni snijeg", 80: "pljuskovi", 81: "pljuskovi", 82: "jaki pljuskovi",
         85: "snježni pljuskovi", 86: "snježni pljuskovi", 95: "grmljavina",
         96: "grmljavina s gradom", 99: "grmljavina s gradom"}
    return t.get(code, "")


def draw_icon(d, kind, cx, cy, s, ink=0):
    """Jednostavne linijske ikone. s = velicina (sirina)."""
    lw = max(2, int(s / 18))

    def sun(x, y, r):
        d.ellipse([x - r, y - r, x + r, y + r], outline=ink, width=lw)
        for i in range(8):
            a = i * math.pi / 4
            d.line([x + math.cos(a) * r * 1.45, y + math.sin(a) * r * 1.45,
                    x + math.cos(a) * r * 1.95, y + math.sin(a) * r * 1.95], fill=ink, width=lw)

    def cloud(x, y, w, fill=255):
        h = w * 0.42
        parts = [(x - w * .28, y + h * .05, w * .2), (x, y - h * .22, w * .27), (x + w * .28, y + h * .08, w * .18)]
        base = y + h * .3

        def blob(inset, col):
            for px, py, r in parts:
                d.ellipse([px - r + inset, py - r + inset, px + r - inset, py + r - inset], fill=col)
            d.rectangle([x - w * .28, y + h * .05, x + w * .28, base - inset], fill=col)
        blob(0, ink)
        blob(lw, fill)

    if kind == "sun":
        sun(cx, cy, s * .22)
    elif kind == "partly":
        sun(cx - s * .15, cy - s * .12, s * .16)
        cloud(cx + s * .08, cy + s * .1, s * .7)
    elif kind in ("cloud", "fog", "rain", "snow", "storm"):
        cloud(cx, cy - s * .08, s * .8)
        base = cy + s * .22
        if kind == "fog":
            for i in range(3):
                yy = base + i * s * .08
                d.line([cx - s * .3, yy, cx + s * .3, yy], fill=ink, width=lw)
        elif kind == "rain":
            for i in (-1, 0, 1):
                x = cx + i * s * .18
                d.line([x, base, x - s * .06, base + s * .18], fill=ink, width=lw)
        elif kind == "snow":
            for i in (-1, 0, 1):
                x, y, r = cx + i * s * .18, base + s * .09, s * .05
                d.line([x - r, y, x + r, y], fill=ink, width=lw)
                d.line([x, y - r, x, y + r], fill=ink, width=lw)
                d.line([x - r * .7, y - r * .7, x + r * .7, y + r * .7], fill=ink, width=lw)
                d.line([x - r * .7, y + r * .7, x + r * .7, y - r * .7], fill=ink, width=lw)
        elif kind == "storm":
            pts = [(cx + s * .05, base), (cx - s * .08, base + s * .14), (cx + s * .04, base + s * .14), (cx - s * .06, base + s * .3)]
            d.line(pts, fill=ink, width=lw + 1)
    else:
        d.text((cx, cy), "?", font=font("m", int(s * .5)), fill=ink, anchor="mm")


# ---------------------------------------------------------------- pomocno
def pm_label(v):
    if v is None:
        return "—"
    for lim, t in ((10, "dobar"), (20, "prihvatljiv"), (25, "umjeren"), (50, "loš"), (75, "vrlo loš")):
        if v <= lim:
            return t
    return "izuzetno loš"


def fmt(v, nd=0, unit=""):
    if v is None:
        return "–"
    return (f"{v:.{nd}f}" if nd else f"{round(v)}") + unit


def text_w(d, s, f):
    return d.textlength(s, font=f)


# ---------------------------------------------------------------- crtanje
def render(weather, air, pur, now):
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    M = 40
    y = 34

    # zaglavlje
    d.text((M, y), DANI[now.weekday()], font=font("b", 64), fill=0)
    d.text((M, y + 78), f"{now.day}. {MJESECI[now.month - 1]} {now.year}", font=font("r", 30), fill=0)
    f_small = font("r", 24)
    d.text((W - M, y + 12), CITY, font=f_small, fill=60, anchor="ra")
    d.text((W - M, y + 44), f"ažurirano {now:%H:%M}", font=f_small, fill=60, anchor="ra")
    y += 130
    d.line([M, y, W - M, y], fill=0, width=3)

    # trenutno vrijeme
    y += 30
    cur = (weather or {}).get("current", {})
    daily = (weather or {}).get("daily", {})
    kind = wmo_kind(cur.get("weather_code"))
    draw_icon(d, kind, M + 85, y + 80, 170)
    d.text((M + 200, y + 5), fmt(cur.get("temperature_2m"), unit="°"), font=font("b", 120), fill=0)
    d.text((M + 205, y + 140), wmo_text(cur.get("weather_code")), font=font("r", 28), fill=0)
    d.text((M + 205, y + 176), f"osjećaj {fmt(cur.get('apparent_temperature'), unit='°')}", font=font("r", 24), fill=70)
    if daily.get("temperature_2m_max"):
        d.text((W - M, y + 40), f"max {fmt(daily['temperature_2m_max'][0], unit='°')}  min {fmt(daily['temperature_2m_min'][0], unit='°')}",
               font=font("m", 26), fill=0, anchor="ra")
    d.text((W - M, y + 80), f"vjetar {fmt(cur.get('wind_speed_10m'))} km/h", font=font("r", 24), fill=0, anchor="ra")

    # prognoza 3 dana
    y += 212
    d.line([M, y, W - M, y], fill=120, width=2)
    colw = (W - 2 * M) / 3
    times = daily.get("time", [])
    for i in range(1, 4):
        if i >= len(times):
            break
        day = dt.date.fromisoformat(times[i])
        cx = M + colw * (i - 1) + colw / 2
        d.text((cx, y + 18), DANI_K[day.weekday()], font=font("m", 28), fill=0, anchor="ma")
        draw_icon(d, wmo_kind(daily["weather_code"][i]), cx, y + 100, 90)
        d.text((cx, y + 160), f"{fmt(daily['temperature_2m_max'][i], unit='°')} / {fmt(daily['temperature_2m_min'][i], unit='°')}",
               font=font("r", 28), fill=0, anchor="ma")
    y += 196
    d.line([M, y, W - M, y], fill=120, width=2)

    # dnevni boravak (preciscac)
    y += 22
    d.text((M, y), "Dnevni boravak", font=font("m", 26), fill=0)
    y += 44
    gap = 18
    bw = (W - 2 * M - 2 * gap) / 3
    pur = pur or {}
    boxes = [(fmt(pur.get("temperature"), 1, "°") if pur.get("temperature") is not None else "–", "temperatura"),
             (fmt(pur.get("humidity"), unit="%"), "vlaga"),
             (fmt(pur.get("pm25")), "PM2.5")]
    for i, (val, lab) in enumerate(boxes):
        x0 = M + i * (bw + gap)
        d.rounded_rectangle([x0, y, x0 + bw, y + 118], radius=14, outline=0, width=3)
        d.text((x0 + bw / 2, y + 18), val, font=font("b", 54), fill=0, anchor="ma")
        d.text((x0 + bw / 2, y + 82), lab, font=font("r", 22), fill=50, anchor="ma")
    y += 118 + 22

    # vani zrak (crna traka)
    aq = (air or {}).get("current", {})
    pm = aq.get("pm2_5")
    d.rounded_rectangle([M, y, W - M, y + 80], radius=14, fill=0)
    d.text((M + 24, y + 40), "Vani zrak", font=font("m", 28), fill=255, anchor="lm")
    d.text((W - M - 24, y + 40), f"PM2.5 {fmt(pm)} · {pm_label(pm)}", font=font("b", 34), fill=255, anchor="rm")
    y += 80 + 20

    # savjet
    ipm = pur.get("pm25")
    if pm is not None and pm > 25:
        tip = "Zrak vani je loš: ne provjetravaj."
        if ipm is not None and ipm > 15:
            tip = "Zrak loš i vani i unutra: pojačaj prečistač."
    elif pm is not None and ipm is not None and ipm > pm + 10:
        tip = "Unutra je lošije nego vani: provjetri."
    else:
        tip = ""
    if tip:
        d.text((W / 2, y + 4), tip, font=font("m", 26), fill=0, anchor="ma")

    # podnozje
    fy = H - 52
    d.line([M, fy - 16, W - M, fy - 16], fill=150, width=1)
    if pur:
        mode = MODES.get(pur.get("mode"), "")
        state = "isključen" if pur.get("power") is False else (mode or "uključen")
        left = f"Prečistač: {state} · filter {fmt(pur.get('filter'), unit='%')}"
    else:
        left = "Prečistač: nedostupan"
    d.text((M, fy), left, font=font("r", 22), fill=40)
    if daily.get("sunrise"):
        sr = daily["sunrise"][0][-5:]
        ss = daily["sunset"][0][-5:]
        d.text((W - M, fy), f"izlazak {sr} · zalazak {ss}", font=font("r", 22), fill=40, anchor="ra")

    # 16 nijansi sive (e-ink)
    img = img.point(lambda v: (v // 17) * 17)
    return img


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    now = dt.datetime.now(TZ)
    weather = safe(get_weather, "vrijeme")
    air = safe(get_air, "zrak")
    pur = safe(get_purifier, "xiaomi")
    img = render(weather, air, pur, now)
    path = os.path.join(OUT_DIR, "dashboard.png")
    img.save(path, optimize=True)
    with open(os.path.join(OUT_DIR, "index.html"), "w") as f:
        f.write('<!doctype html><meta charset="utf-8"><title>Kindle dashboard</title>'
                '<img src="dashboard.png" style="max-width:100%;border:1px solid #ccc">')
    print("Sačuvano:", path)
    if weather is None and air is None and pur is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
