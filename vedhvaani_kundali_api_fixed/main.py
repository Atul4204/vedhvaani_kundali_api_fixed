from fastapi import FastAPI
import swisseph as swe
from datetime import datetime

app = FastAPI()

@app.get("/")
def home():
    return {"message": "VedhVaani Kundali API is running"}

@app.get("/kundali")
def kundali(date: str, time: str, lat: float, lon: float):
    try:
        # Parse date and time
        dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        jd = swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60.0)

        # Example: Sun position
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
