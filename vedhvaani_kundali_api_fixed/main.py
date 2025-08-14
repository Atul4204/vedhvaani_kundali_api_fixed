from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
import swisseph as swe
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os

app = FastAPI()

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
def generate_kundali(date: str, time: str, lat: float, lon: float, lang: str = "hi", style: str = "north"):
    # Placeholder: In real version, here we generate detailed kundali in desired language
    return {
        "language": lang,
        "style": style,
        "date": date,
        "time": time,
        "location": {"lat": lat, "lon": lon},
        "rashifal": "यह एक डेमो राशिफल है।"
    }

@app.get("/generate_kundali_pdf")
def generate_kundali_pdf(date: str, time: str, lat: float, lon: float, lang: str = "hi", style: str = "north"):
    # Create PDF file
    filename = f"kundali_{date}_{time.replace(':','-')}.pdf"
    filepath = f"/tmp/{filename}"
    c = canvas.Canvas(filepath, pagesize=A4)
    c.drawString(100, 800, f"Kundali Report ({lang.upper()}, {style.title()} Indian Style)")
    c.drawString(100, 780, f"Date: {date}  Time: {time}")
    c.drawString(100, 760, f"Latitude: {lat}  Longitude: {lon}")
    c.drawString(100, 740, "Rashifal: यह एक डेमो पीडीएफ है।")
    c.save()

    return FileResponse(filepath, media_type="application/pdf", filename=filename)
