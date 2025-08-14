# main.py
from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
import swisseph as swe
from datetime import datetime
import tempfile
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
import os
import math

# Optional: set ephemeris path from env
EPHE_PATH = os.getenv("SW_EPHE_PATH")
if EPHE_PATH:
    swe.set_ephe_path(EPHE_PATH)

app = FastAPI(title="VedhVaani Kundali Engine - Professional")

# Multilingual texts
rashifal_text = {
    "hi": "यह एक डेमो राशिफल है।",
    "mr": "हा एक डेमो राशिभविष्य आहे.",
    "en": "This is a demo horoscope."
}

# Graha names in hi/mr/en (order must match code usage)
graha_names = {
    "hi": ["सूर्य", "चंद्र", "मंगल", "बुध", "बृहस्पति", "शुक्र", "शनि", "राहु", "केतु"],
    "mr": ["सूर्य", "चंद्र", "मंगळ", "बुध", "गुरू", "शुक्र", "शनी", "राहु", "केतु"],
    "en": ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
}

# planet color mapping (both english & hindi keys supported)
planet_colors = {
    "Sun": colors.red, "सूर्य": colors.red,
    "Moon": colors.gray, "चंद्र": colors.gray,
    "Mars": colors.orange, "मंगल": colors.orange,
    "Mercury": colors.green, "बुध": colors.green,
    "Jupiter": colors.blue, "बृहस्पति": colors.blue,
    "Venus": colors.pink, "शुक्र": colors.pink,
    "Saturn": colors.black, "शनि": colors.black,
    "Rahu": colors.brown, "राहु": colors.brown,
    "Ketu": colors.purple, "केतु": colors.purple
}

# Request model
class KundaliRequest(BaseModel):
    name: str
    date: str      # YYYY-MM-DD
    time: str      # HH:MM (24h)
    lat: float
    lon: float
    lang: str = "hi"    # hi/mr/en
    style: str = "north" # north/south
    hsys: str = "P"     # house system for swe.houses: 'P' (Placidus) default; you can change if needed

# -------------------------
# Safe swiss-ephemeris helpers
# -------------------------
def safe_calc_ut(jd, planet):
    """
    Robustly call swe.calc_ut and return longitude (float).
    """
    result = swe.calc_ut(jd, planet)
    # result is usually a tuple whose first element is longitude (float).
    lon = None
    try:
        first = result[0]
        if isinstance(first, (list, tuple)):
            # sometimes nested
            lon = float(first[0])
        else:
            lon = float(first)
    except Exception:
        # fallback: scan for first numeric element
        for item in result:
            try:
                lon = float(item)
                break
            except Exception:
                continue
    if lon is None:
        raise RuntimeError(f"Cannot parse calc_ut result: {result}")
    return lon

def safe_houses(jd, lat, lon, hsys="P"):
    """
    Robustly call swe.houses and try to extract ascendant longitude.
    Returns tuple (ascendant_longitude_in_degrees, cusps_list_optional)
    """
    result = swe.houses(jd, lat, lon, hsys)
    asc = None
    cusps = None
    # Common return formats:
    # - (cusps_list, ascmc_list)
    # - (ascmc_list, ) etc. We'll attempt to find asc in nested arrays.
    try:
        if isinstance(result, (list, tuple)):
            # Try patterns
            # Pattern A: (cusps, ascmc)
            if len(result) >= 2:
                maybe_ascmc = result[1]
                if isinstance(maybe_ascmc, (list, tuple)) and len(maybe_ascmc) >= 1:
                    # ascmc[0] often is ascendant
                    asc = float(maybe_ascmc[0])
                    cusps = result[0]
            # Pattern B: result itself is ascmc-like (first element)
            if asc is None:
                first = result[0]
                if isinstance(first, (list, tuple)):
                    # try first[0]
                    try:
                        asc = float(first[0])
                    except Exception:
                        asc = None
            # Pattern C: sometimes returned as dict-like or flat tuple; try to find a value in range 0..360
            if asc is None:
                # scan nested for a plausible asc (0<=x<360)
                def scan(obj):
                    if isinstance(obj, (list, tuple)):
                        for el in obj:
                            val = scan(el)
                            if val is not None:
                                return val
                    else:
                        try:
                            f = float(obj)
                            if 0.0 <= f < 360.0:
                                return f
                        except Exception:
                            return None
                    return None
                asc = scan(result)
    except Exception:
        asc = None
    if asc is None:
        raise RuntimeError(f"Unable to extract ascendant from swe.houses result: {result}")
    # normalize
    asc = asc % 360.0
    return asc, cusps

# house number (1..12) relative to ascendant
def get_house_number(planet_long, asc_long):
    diff = (planet_long - asc_long) % 360.0
    house = int(diff // 30) + 1
    if house > 12:
        house -= 12
    return house

# -------------------------
# Chart drawing helpers (professional, multi-planet per house)
# -------------------------
def draw_north_chart(c, planets, asc_long, lang):
    x0, y0 = 220, 420
    size = 260
    c.setLineWidth(1.5)
    c.rect(x0, y0, size, size)
    # diamond
    c.line(x0, y0+size/2, x0+size/2, y0+size)
    c.line(x0+size/2, y0+size, x0+size, y0+size/2)
    c.line(x0+size, y0+size/2, x0+size/2, y0)
    c.line(x0+size/2, y0, x0, y0+size/2)

    # tuned house centers for nicer layout
    house_centers = {
        1: (x0+size/2, y0+8), 2: (x0+size-20, y0+size/4+8), 3: (x0+size-30, y0+3*size/4-12),
        4: (x0+size/2, y0+size-8), 5: (x0+12, y0+3*size/4-12), 6: (x0+12, y0+size/4+8),
        7: (x0+size/2, y0+size/2), 8: (x0+size/4-8, y0+size/2), 9: (x0+3*size/4+10, y0+size/2),
        10: (x0+size/4-8, y0+3*size/4-8), 11: (x0+3*size/4+10, y0+3*size/4-8), 12: (x0+size/4-8, y0+size/4+8)
    }

    # bucket planets
    house_planets = {i: [] for i in range(1,13)}
    for graha, lon in planets.items():
        house = get_house_number(lon, asc_long)
        house_planets[house].append(graha)

    # draw planets (stacked)
    for house in range(1,13):
        cx, cy = house_centers[house]
        plist = house_planets[house]
        for i, graha in enumerate(plist):
            color = planet_colors.get(graha, colors.black)
            c.setFillColor(color)
            c.setFont("Helvetica", 9)
            c.drawString(cx - 20, cy - 6 - i*12, graha)
    c.setFillColor(colors.black)

def draw_south_chart(c, planets, asc_long, lang):
    x0, y0 = 220, 420
    size = 260
    box_w = size/3
    box_h = size/4
    c.setLineWidth(1.5)
    c.rect(x0, y0, size, size)
    # grid
    for i in range(1,3):
        c.line(x0 + i*box_w, y0, x0 + i*box_w, y0 + size)
    for j in range(1,4):
        c.line(x0, y0 + j*box_h, x0 + size, y0 + j*box_h)

    # mapping house centers (south style)
    house_centers = {
        1: (x0+box_w, y0+5), 2: (x0+2*box_w, y0+5), 3: (x0+2*box_w, y0+box_h+5),
        4: (x0+2*box_w, y0+2*box_h+5), 5: (x0+2*box_w, y0+3*box_h+5), 6: (x0+box_w, y0+3*box_h+5),
        7: (x0+5, y0+3*box_h+5), 8: (x0+5, y0+2*box_h+5), 9: (x0+5, y0+box_h+5),
        10: (x0+5, y0+5), 11: (x0+box_w, y0+box_h+5), 12: (x0+2*box_w, y0+box_h+5)
    }

    house_planets = {i: [] for i in range(1,13)}
    for graha, lon in planets.items():
        house = get_house_number(lon, asc_long)
        house_planets[house].append(graha)

    for house in range(1,13):
        cx, cy = house_centers[house]
        plist = house_planets[house]
        for i, graha in enumerate(plist):
            color = planet_colors.get(graha, colors.black)
            c.setFillColor(color)
            c.setFont("Helvetica", 9)
            c.drawString(cx - 15, cy - 6 - i*12, graha)
    c.setFillColor(colors.black)

# -------------------------
# Core endpoints
# -------------------------
@app.post("/kundali")
def kundali(req: KundaliRequest):
    """
    Return full kundali result as JSON.
    """
    try:
        # parse date/time
        dt = datetime.strptime(f"{req.date} {req.time}", "%Y-%m-%d %H:%M")
        # julian day in UT (note: no timezone handling — ensure you pass UTC or local converted to UT)
        jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute/60.0)
        # set topo (lon, lat, height)
        swe.set_topo(req.lon, req.lat, 0)

        # calculate planets
        planets = {
            graha_names[req.lang][0]: safe_calc_ut(jd, swe.SUN),
            graha_names[req.lang][1]: safe_calc_ut(jd, swe.MOON),
            graha_names[req.lang][2]: safe_calc_ut(jd, swe.MARS),
            graha_names[req.lang][3]: safe_calc_ut(jd, swe.MERCURY),
            graha_names[req.lang][4]: safe_calc_ut(jd, swe.JUPITER),
            graha_names[req.lang][5]: safe_calc_ut(jd, swe.VENUS),
            graha_names[req.lang][6]: safe_calc_ut(jd, swe.SATURN),
            graha_names[req.lang][7]: safe_calc_ut(jd, swe.MEAN_NODE),
        }
        # Ketu opposite of Rahu
        rahu_lon = planets[graha_names[req.lang][7]]
        planets[graha_names[req.lang][8]] = (rahu_lon + 180.0) % 360.0

        # ascendant via houses
        asc_long, cusps = safe_houses(jd, req.lat, req.lon, req.hsys)

        # compute houses mapping for output (list of planets per house)
        house_planets = {i: [] for i in range(1,13)}
        for graha, lon in planets.items():
            house = get_house_number(lon, asc_long)
            house_planets[house].append({"name": graha, "longitude": round(lon, 4)})

        # demo dasha (you can replace with real dasha logic)
        dasha = [
            {"name": f"Mahadasha - {graha_names[req.lang][0]}", "start": "2025-01-01", "end": "2031-01-01"},
            {"name": f"Mahadasha - {graha_names[req.lang][1]}", "start": "2031-01-01", "end": "2041-01-01"}
        ]

        resp = {
            "name": req.name,
            "date_time": dt.isoformat(),
            "lang": req.lang,
            "style": req.style,
            "hsys": req.hsys,
            "graha_positions": {g: round(l, 6) for g, l in planets.items()},
            "ascendant": {"longitude": round(asc_long, 6), "degree_in_sign": round(asc_long % 30.0, 4), "sign_index": int(asc_long // 30) + 1},
            "houses": house_planets,
            "rashifal": rashifal_text.get(req.lang, rashifal_text["en"]),
            "dasha": dasha
        }
        return resp
    except Exception as e:
        return {"error": str(e)}

@app.post("/kundali-pdf")
def kundali_pdf(req: KundaliRequest):
    """
    Generate a professional PDF and return as FileResponse.
    """
    try:
        dt = datetime.strptime(f"{req.date} {req.time}", "%Y-%m-%d %H:%M")
        jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute/60.0)
        swe.set_topo(req.lon, req.lat, 0)

        planets = {
            graha_names[req.lang][0]: safe_calc_ut(jd, swe.SUN),
            graha_names[req.lang][1]: safe_calc_ut(jd, swe.MOON),
            graha_names[req.lang][2]: safe_calc_ut(jd, swe.MARS),
            graha_names[req.lang][3]: safe_calc_ut(jd, swe.MERCURY),
            graha_names[req.lang][4]: safe_calc_ut(jd, swe.JUPITER),
            graha_names[req.lang][5]: safe_calc_ut(jd, swe.VENUS),
            graha_names[req.lang][6]: safe_calc_ut(jd, swe.SATURN),
            graha_names[req.lang][7]: safe_calc_ut(jd, swe.MEAN_NODE),
        }
        planets[graha_names[req.lang][8]] = (planets[graha_names[req.lang][7]] + 180.0) % 360.0

        asc_long, cusps = safe_houses(jd, req.lat, req.lon, req.hsys)

        # prepare pdf
        safe_name = "".join([c if c.isalnum() or c in (" ", "_", "-") else "_" for c in req.name]).strip()
        filename = f"kundali_{safe_name}_{req.date}.pdf"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        c = canvas.Canvas(tmp.name, pagesize=A4)
        # header
        c.setFont("Helvetica-Bold", 18)
        c.drawString(140, 800, "VedhVaani — Kundali Report")
        c.setFont("Helvetica", 11)
        c.drawString(50, 780, f"Name: {req.name}")
        c.drawString(50, 766, f"DOB: {req.date}  TOB: {req.time}")
        c.drawString(50, 752, f"Location: {req.lat}, {req.lon}   Style: {req.style}   Lang: {req.lang}")

        # rashifal box
        c.setLineWidth(0.8)
        c.rect(45, 720, 520, 36, stroke=1, fill=0)
        c.setFont("Helvetica-Oblique", 10)
        c.drawString(50, 730, f"Rashifal: {rashifal_text.get(req.lang, rashifal_text['en'])}")

        # draw chart
        if req.style == "north":
            draw_north_chart(c, planets, asc_long, req.lang)
        else:
            draw_south_chart(c, planets, asc_long, req.lang)

        # Graha positions table
        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, 320, "Graha Positions (Longitude):")
        c.setFont("Helvetica", 11)
        y = 302
        for graha, lon in planets.items():
            c.drawString(60, y, f"{graha}: {lon:.4f}°")
            y -= 14

        # Ascendant box
        asc_sign_idx = int(asc_long // 30) + 1
        asc_deg_in_sign = asc_long % 30.0
        c.setFont("Helvetica-Bold", 12)
        c.drawString(340, 320, "Ascendant (Lagna):")
        c.setFont("Helvetica", 11)
        c.drawString(340, 302, f"Longitude: {asc_long:.4f}°")
        c.drawString(340, 286, f"Sign Index (1..12): {asc_sign_idx}")
        c.drawString(340, 270, f"Degree in Sign: {asc_deg_in_sign:.3f}°")

        # Dasha (demo)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, 220, "Dasha (Demo):")
        c.setFont("Helvetica", 11)
        y = 200
        dasha = [
            {"name": f"Mahadasha - {graha_names[req.lang][0]}", "start": "2025-01-01", "end": "2031-01-01"},
            {"name": f"Mahadasha - {graha_names[req.lang][1]}", "start": "2031-01-01", "end": "2041-01-01"}
        ]
        for d in dasha:
            c.drawString(60, y, f"{d['name']}: {d['start']} → {d['end']}")
            y -= 14

        # houses listing (compact)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(50, 140, "Houses (planets in each):")
        c.setFont("Helvetica", 10)
        y = 122
        # compute house planets for display
        house_planets = {i: [] for i in range(1,13)}
        for graha, lon in planets.items():
            house = get_house_number(lon, asc_long)
            house_planets[house].append(graha)
        for house in range(1,13):
            plist = ", ".join(house_planets[house]) if house_planets[house] else "-"
            c.drawString(60, y, f"House {house}: {plist}")
            y -= 12

        # footer
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(50, 40, "Generated by VedhVaani Kundali Engine")

        c.showPage()
        c.save()

        return FileResponse(tmp.name, filename=filename, media_type="application/pdf")
    except Exception as e:
        return {"error": str(e)}
