from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
import swisseph as swe
from datetime import datetime
import tempfile
import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = FastAPI()

# Demo translations (extend for real astrology texts)
rashifal_text = {
    "hi": "यह एक डेमो राशिफल है।",
    "mr": "हा एक डेमो राशिभविष्य आहे.",
    "en": "This is a demo horoscope."
}

@app.get("/")
def home():
    return {"message": "VedhVaani Kundali API is running"}

@app.get("/kundali")
def kundali(date: str, time: str, lat: float, lon: float):
    try:
        dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60.0)
        swe.set_topo(lon, lat, 0)
        sun_pos = swe.calc_ut(jd, swe.SUN)
        return {
            "julian_day": jd,
            "sun_longitude": sun_pos[0],
            "sun_latitude": sun_pos[1],
            "date_time": dt.isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/generate_kundali")
def generate_kundali(
    date: str,
    time: str,
    lat: float,
    lon: float,
    lang: str = Query("hi", enum=["hi", "mr", "en"]),
    style: str = Query("north", enum=["north", "south"])
):
    try:
        dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60.0)
        swe.set_topo(lon, lat, 0)

        planets = {
            "Sun": swe.calc_ut(jd, swe.SUN)[0],
            "Moon": swe.calc_ut(jd, swe.MOON)[0],
            "Mars": swe.calc_ut(jd, swe.MARS)[0],
            "Mercury": swe.calc_ut(jd, swe.MERCURY)[0],
            "Jupiter": swe.calc_ut(jd, swe.JUPITER)[0],
            "Venus": swe.calc_ut(jd, swe.VENUS)[0],
            "Saturn": swe.calc_ut(jd, swe.SATURN)[0],
            "Rahu": swe.calc_ut(jd, swe.MEAN_NODE)[0],
            "Ketu": (swe.calc_ut(jd, swe.MEAN_NODE)[0] + 180) % 360
        }

        # Demo Lagna calculation
        lagna = (lon + lat) % 360

        # Demo Dasha
        dasha = [
            {"name": "Mahadasha - Sun", "start": "2025-01-01", "end": "2031-01-01"},
            {"name": "Mahadasha - Moon", "start": "2031-01-01", "end": "2041-01-01"}
        ]

        return {
            "date_time": dt.isoformat(),
            "style": style,
            "graha_positions": planets,
            "lagna": lagna,
            "rashifal": rashifal_text[lang],
            "dasha": dasha
        }
    except Exception as e:
        return {"error": str(e)}

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
        data = generate_kundali(date, time, lat, lon, lang, style)

        # Create PDF in temp file
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        c = canvas.Canvas(temp_file.name, pagesize=A4)

        c.setFont("Helvetica-Bold", 16)
        c.drawString(200, 800, "VedhVaani Kundali Report")

        c.setFont("Helvetica", 12)
        c.drawString(50, 770, f"Date & Time: {data['date_time']}")
        c.drawString(50, 750, f"Style: {data['style']}")
        c.drawString(50, 730, f"Rashifal: {data['rashifal']}")

        c.drawString(50, 700, "Graha Positions:")
        y = 680
        for graha, pos in data["graha_positions"].items():
            c.drawString(60, y, f"{graha}: {pos:.2f}")
            y -= 20

        c.drawString(50, y, "Dasha Periods:")
        y -= 20
        for d in data["dasha"]:
            c.drawString(60, y, f"{d['name']}: {d['start']} to {d['end']}")
            y -= 20

        c.showPage()
        c.save()

        return FileResponse(temp_file.name, filename="kundali_report.pdf", media_type="application/pdf")
    except Exception as e:
        return {"error": str(e)}
