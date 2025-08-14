from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
import swisseph as swe
from datetime import datetime
import tempfile
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors

app = FastAPI()

# Multilingual texts
rashifal_text = {
    "hi": "यह एक डेमो राशिफल है।",
    "mr": "हा एक डेमो राशिभविष्य आहे.",
    "en": "This is a demo horoscope."
}

graha_names = {
    "hi": ["सूर्य", "चंद्र", "मंगल", "बुध", "बृहस्पति", "शुक्र", "शनि", "राहु", "केतु"],
    "mr": ["सूर्य", "चंद्र", "मंगळ", "बुध", "गुरू", "शुक्र", "शनी", "राहु", "केतु"],
    "en": ["Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn", "Rahu", "Ketu"]
}

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

# Helper functions
def get_planet_longitude(planet, jd):
    result = swe.calc_ut(jd, planet)
    if isinstance(result[0], (tuple, list)):
        return result[0][0]
    return result[0]

def get_house_number(planet_long, lagna):
    diff = (planet_long - lagna) % 360
    house = int(diff // 30) + 1
    if house > 12:
        house -= 12
    return house

# Draw North Indian chart
def draw_north_chart(c, planets, lagna, lang):
    x0, y0 = 250, 400
    size = 250
    c.setLineWidth(1.5)
    c.rect(x0, y0, size, size)

    # Draw diamond
    c.line(x0, y0+size/2, x0+size/2, y0+size)
    c.line(x0+size/2, y0+size, x0+size, y0+size/2)
    c.line(x0+size, y0+size/2, x0+size/2, y0)
    c.line(x0+size/2, y0, x0, y0+size/2)

    # House centers
    house_centers = {
        1: (x0+size/2, y0), 2: (x0+size, y0+size/4), 3: (x0+size, y0+3*size/4),
        4: (x0+size/2, y0+size), 5: (x0, y0+3*size/4), 6: (x0, y0+size/4),
        7: (x0+size/2, y0+size/2), 8: (x0+size/4, y0+size/2), 9: (x0+3*size/4, y0+size/2),
        10: (x0+size/4, y0+3*size/4), 11: (x0+3*size/4, y0+3*size/4), 12: (x0+size/4, y0+size/4)
    }

    # Multiple planets per house
    house_planets = {i: [] for i in range(1,13)}
    for graha, long in planets.items():
        house = get_house_number(long, lagna)
        house_planets[house].append(graha)

    for house, plist in house_planets.items():
        x, y = house_centers[house]
        for i, graha in enumerate(plist):
            color = planet_colors.get(graha, colors.black)
            c.setFillColor(color)
            c.drawString(x-15, y-10 - i*12, graha)
    c.setFillColor(colors.black)

# Draw South Indian chart
def draw_south_chart(c, planets, lagna, lang):
    x0, y0 = 250, 400
    size = 250
    box_w = size/3
    box_h = size/4
    c.setLineWidth(1.5)
    c.rect(x0, y0, size, size)

    for i in range(3):
        c.line(x0 + i*box_w, y0, x0 + i*box_w, y0 + size)
    for j in range(4):
        c.line(x0, y0 + j*box_h, x0 + size, y0 + j*box_h)

    house_centers = {
        1: (x0 + box_w, y0), 2: (x0 + 2*box_w, y0), 3: (x0 + 2*box_w, y0 + box_h),
        4: (x0 + 2*box_w, y0 + 2*box_h), 5: (x0 + 2*box_w, y0 + 3*box_h), 6: (x0 + box_w, y0 + 3*box_h),
        7: (x0, y0 + 3*box_h), 8: (x0, y0 + 2*box_h), 9: (x0, y0 + box_h),
        10: (x0, y0), 11: (x0 + box_w, y0 + box_h), 12: (x0 + 2*box_w, y0 + box_h)
    }

    house_planets = {i: [] for i in range(1,13)}
    for graha, long in planets.items():
        house = get_house_number(long, lagna)
        house_planets[house].append(graha)

    for house, plist in house_planets.items():
        x, y = house_centers[house]
        for i, graha in enumerate(plist):
            color = planet_colors.get(graha, colors.black)
            c.setFillColor(color)
            c.drawString(x-15, y-10 - i*12, graha)
    c.setFillColor(colors.black)

# PDF Generation Endpoint
@app.get("/generate_kundali_pdf")
def generate_kundali_pdf(
    date: str,
    time: str,
    lat: float,
    lon: float,
    lang: str = Query("hi", enum=["hi", "mr", "en"]),
    style: str = Query("north", enum=["north", "south"])
):
    try:
        dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute/60.0)
        swe.set_topo(lon, lat, 0)

        planets = {
            graha_names[lang][0]: get_planet_longitude(swe.SUN, jd),
            graha_names[lang][1]: get_planet_longitude(swe.MOON, jd),
            graha_names[lang][2]: get_planet_longitude(swe.MARS, jd),
            graha_names[lang][3]: get_planet_longitude(swe.MERCURY, jd),
            graha_names[lang][4]: get_planet_longitude(swe.JUPITER, jd),
            graha_names[lang][5]: get_planet_longitude(swe.VENUS, jd),
            graha_names[lang][6]: get_planet_longitude(swe.SATURN, jd),
            graha_names[lang][7]: get_planet_longitude(swe.MEAN_NODE, jd),
            graha_names[lang][8]: (get_planet_longitude(swe.MEAN_NODE, jd)+180)%360
        }

        lagna = (lon + lat) % 360

        dasha = [
            {"name": f"Mahadasha - {graha_names[lang][0]}", "start": "2025-01-01", "end": "2031-01-01"},
            {"name": f"Mahadasha - {graha_names[lang][1]}", "start": "2031-01-01", "end": "2041-01-01"}
        ]

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        c = canvas.Canvas(temp_file.name, pagesize=A4)

        # Header
        c.setFont("Helvetica-Bold", 18)
        c.drawString(150, 800, "VedhVaani Kundali Report")
        c.setFont("Helvetica", 12)
        c.drawString(50, 770, f"Date & Time: {dt.isoformat()}")
        c.drawString(50, 750, f"Style: {style}")
        c.drawString(50, 730, f"Rashifal: {rashifal_text[lang]}")

        # Draw chart
        if style=="north":
            draw_north_chart(c, planets, lagna, lang)
        else:
            draw_south_chart(c, planets, lagna, lang)

        # Graha positions
        y = 200
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y+60, "Graha Positions:")
        c.setFont("Helvetica", 12)
        for graha, pos in planets.items():
            y -= 20
            c.drawString(60, y+60, f"{graha}: {pos:.2f}")

        # Dasha periods
        y -= 40
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, y+60, "Dasha Periods:")
        c.setFont("Helvetica", 12)
        for d in dasha:
            y -= 20
            c.drawString(60, y+60, f"{d['name']}: {d['start']} to {d['end']}")

        c.showPage()
        c.save()

        return FileResponse(temp_file.name, filename="kundali_report.pdf", media_type="application/pdf")

    except Exception as e:
        return {"error": str(e)}
