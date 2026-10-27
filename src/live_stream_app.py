"""
Duck-Vision Live Stream - Flask-app som viser duck_vision_live.jpg som en enkel
"stream" via auto-refresh, pluss litt statusinfo fra MQTT-status-filen om den finnes.

Kjør: .venv/bin/python3 src/live_stream_app.py
Standard port: 8090
"""

from __future__ import annotations

import io
import time
from datetime import datetime
from pathlib import Path

import requests
from flask import Flask, Response, jsonify, render_template_string
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path(__file__).resolve().parents[1]
LIVE_IMAGE_PATH = BASE_DIR / "data" / "logs" / "duck_vision_live.jpg"

# Åmot i Sokndal, Rogaland
WEATHER_LAT = 58.3463
WEATHER_LON = 6.3182
WEATHER_LOCATION_NAME = "Åmot, Sokndal"
WEATHER_CACHE_SEC = 600  # MET/Yr ber om maks ett kall hvert 10. minutt

# MET Norway (Yr) krever en identifiserbar User-Agent, se api.met.no/doc/TermsOfService
# "complete" (ikke "compact") brukes fordi den inkluderer wind_speed_of_gust
WEATHER_API_URL = "https://api.met.no/weatherapi/locationforecast/2.0/complete"
NOWCAST_API_URL = "https://api.met.no/weatherapi/nowcast/2.0/complete"
WEATHER_HEADERS = {"User-Agent": "Duck-Vision/1.0 github.com/admog/Duck-Vision"}

_weather_cache: dict = {"data": None, "fetched_at": 0.0}

# Grov mapping fra Yr sine symbol_code-verdier til emoji
_SYMBOL_EMOJI = {
    "clearsky": "☀️",
    "fair": "🌤️",
    "partlycloudy": "⛅",
    "cloudy": "☁️",
    "rainshowers": "🌦️",
    "rainshowersandthunder": "⛈️",
    "sleetshowers": "🌨️",
    "snowshowers": "🌨️",
    "rain": "🌧️",
    "heavyrain": "🌧️",
    "heavyrainandthunder": "⛈️",
    "sleet": "🌨️",
    "snow": "❄️",
    "snowandthunder": "⛈️",
    "fog": "🌫️",
    "sleetshowersandthunder": "⛈️",
    "snowshowersandthunder": "⛈️",
    "thunder": "⛈️",
    "lightrain": "🌦️",
    "lightrainshowers": "🌦️",
    "lightsnow": "🌨️",
    "lightsnowshowers": "🌨️",
    "lightsleet": "🌨️",
    "lightsleetshowers": "🌨️",
}


def _symbol_to_emoji(symbol_code: str) -> str:
    base = (symbol_code or "").split("_")[0]  # strip _day/_night/_polartwilight suffiks
    return _SYMBOL_EMOJI.get(base, "🌡️")


# Norske beskrivelser av Yr sine symbol_code-verdier, til bruk i modal-visning
_SYMBOL_DESCRIPTION_NO = {
    "clearsky": "Klarvær",
    "fair": "Lettskyet",
    "partlycloudy": "Delvis skyet",
    "cloudy": "Overskyet",
    "rainshowers": "Regnbyger",
    "rainshowersandthunder": "Regnbyger og torden",
    "sleetshowers": "Sluddbyger",
    "snowshowers": "Snøbyger",
    "rain": "Regn",
    "heavyrain": "Kraftig regn",
    "heavyrainandthunder": "Kraftig regn og torden",
    "sleet": "Sludd",
    "snow": "Snø",
    "snowandthunder": "Snø og torden",
    "fog": "Tåke",
    "sleetshowersandthunder": "Sluddbyger og torden",
    "snowshowersandthunder": "Snøbyger og torden",
    "thunder": "Torden",
    "lightrain": "Lett regn",
    "lightrainshowers": "Lette regnbyger",
    "lightsnow": "Lett snø",
    "lightsnowshowers": "Lette snøbyger",
    "lightsleet": "Lett sludd",
    "lightsleetshowers": "Lette sluddbyger",
}


def _symbol_to_description(symbol_code: str) -> str:
    base = (symbol_code or "").split("_")[0]
    return _SYMBOL_DESCRIPTION_NO.get(base, "Ukjent værtype")


_COMPASS_POINTS = ["N", "NØ", "Ø", "SØ", "S", "SV", "V", "NV"]


def _degrees_to_compass(degrees) -> str:
    if degrees is None:
        return "--"
    idx = round(degrees / 45) % 8
    return _COMPASS_POINTS[idx]


def _fetch_nowcast() -> dict | None:
    """Radarbasert nedbør og symbol akkurat nå - mer presis enn forecast-modellen for øyeblikket.
    Nowcast dekker kun Norden/Norge og kan feile utenfor dekningsområdet."""
    try:
        resp = requests.get(
            NOWCAST_API_URL,
            params={"lat": WEATHER_LAT, "lon": WEATHER_LON},
            headers=WEATHER_HEADERS,
            timeout=5,
        )
        resp.raise_for_status()
        entry = resp.json()["properties"]["timeseries"][0]["data"]
        return {
            "precipitation_rate": entry["instant"]["details"].get("precipitation_rate"),
            "symbol_code": entry.get("next_1_hours", {}).get("summary", {}).get("symbol_code"),
        }
    except Exception:
        return None


def _build_long_description(symbol_code: str, temperature: float, feels_like, wind_speed: float, precip_probability) -> str:
    """Sett sammen en kort norsk værsetning av det MET faktisk har (de leverer ingen ferdig tekst selv)."""
    parts = [_symbol_to_description(symbol_code) + "."]

    if feels_like is not None and abs(feels_like - temperature) >= 1.0:
        parts.append(f"Kjennes ut som {feels_like:.0f}°C.")

    if wind_speed >= 8.0:
        parts.append("Det er friskt bris eller mer.")
    elif wind_speed >= 5.0:
        parts.append("Litt bris i lufta.")

    if precip_probability is not None and precip_probability >= 15:
        parts.append(f"{precip_probability:.0f}% sjanse for nedbør neste time.")

    return " ".join(parts)


def _fetch_weather() -> dict:
    """Hent værdata for Åmot i Sokndal fra MET/Yr, med enkel in-memory cache."""
    now = time.time()
    if _weather_cache["data"] and (now - _weather_cache["fetched_at"]) < WEATHER_CACHE_SEC:
        return _weather_cache["data"]

    resp = requests.get(
        WEATHER_API_URL,
        params={"lat": WEATHER_LAT, "lon": WEATHER_LON},
        headers=WEATHER_HEADERS,
        timeout=8,
    )
    resp.raise_for_status()
    payload = resp.json()

    timeseries = payload["properties"]["timeseries"]
    now_entry = timeseries[0]
    instant = now_entry["data"]["instant"]["details"]

    # Nedbør/symbol kommer fra next_1_hours når tilgjengelig
    next_hour = now_entry["data"].get("next_1_hours", {})
    symbol_code = next_hour.get("summary", {}).get("symbol_code", "")
    precipitation = next_hour.get("details", {}).get("precipitation_amount", 0.0)

    # Overstyr med radarbasert nåtids-nedbør og -symbol når tilgjengelig (mer presist enn forecast)
    nowcast = _fetch_nowcast()
    nowcast_rate = nowcast.get("precipitation_rate") if nowcast else None
    precipitation_now = nowcast_rate if nowcast_rate is not None else precipitation
    if nowcast and nowcast.get("symbol_code"):
        symbol_code = nowcast["symbol_code"]

    hourly_forecast = _build_hourly_forecast(timeseries)
    daily_forecast = _build_daily_forecast(timeseries)

    feels_like = instant.get("apparent_air_temperature")
    precip_probability = next_hour.get("details", {}).get("probability_of_precipitation")
    long_description = _build_long_description(
        symbol_code=symbol_code,
        temperature=instant.get("air_temperature", 0.0),
        feels_like=feels_like,
        wind_speed=instant.get("wind_speed", 0.0),
        precip_probability=precip_probability,
    )

    result = {
        "location": WEATHER_LOCATION_NAME,
        "temperature": round(instant.get("air_temperature", 0.0), 1),
        "feels_like": round(feels_like, 1) if feels_like is not None else None,
        "wind_speed": round(instant.get("wind_speed", 0.0), 1),
        "wind_gust": round(instant.get("wind_speed_of_gust", 0.0), 1),
        "wind_direction": instant.get("wind_from_direction"),
        "wind_direction_compass": _degrees_to_compass(instant.get("wind_from_direction")),
        "precipitation_mm": round(precipitation_now, 1),
        "precipitation_is_now": nowcast_rate is not None,
        "symbol_code": symbol_code,
        "emoji": _symbol_to_emoji(symbol_code),
        "description": _symbol_to_description(symbol_code),
        "long_description": long_description,
        "updated_at": datetime.fromisoformat(now_entry["time"].replace("Z", "+00:00")).astimezone().strftime("%H:%M"),
        "hourly": hourly_forecast,
        "daily": daily_forecast,
    }


    _weather_cache["data"] = result
    _weather_cache["fetched_at"] = now
    return result


def _build_hourly_forecast(timeseries: list, steps: int = 6, interval_hours: int = 3) -> list:
    """Plukk ut et punkt hver `interval_hours` time, `steps` ganger fremover."""
    forecast = []
    last_time = None
    for entry in timeseries:
        entry_time = datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
        if last_time is not None and (entry_time - last_time).total_seconds() < interval_hours * 3600:
            continue
        next_hour = entry["data"].get("next_1_hours") or entry["data"].get("next_6_hours", {})
        symbol_code = next_hour.get("summary", {}).get("symbol_code", "")
        if not symbol_code:
            continue
        instant = entry["data"]["instant"]["details"]
        forecast.append({
            "time": entry_time.astimezone().strftime("%H:%M"),
            "temperature": round(instant.get("air_temperature", 0.0), 1),
            "emoji": _symbol_to_emoji(symbol_code),
            "description": _symbol_to_description(symbol_code),
            "precipitation_mm": next_hour.get("details", {}).get("precipitation_amount", 0.0),
            "wind_speed": round(instant.get("wind_speed", 0.0), 1),
            "wind_gust": round(instant.get("wind_speed_of_gust", 0.0), 1),
            "wind_direction_compass": _degrees_to_compass(instant.get("wind_from_direction")),
        })
        last_time = entry_time
        if len(forecast) >= steps:
            break
    return forecast


def _build_daily_forecast(timeseries: list, days: int = 4) -> list:
    """Plukk ett punkt rundt kl 12 per kommende dag som dagsprognose."""
    weekdays_no = ["Man", "Tir", "Ons", "Tor", "Fre", "Lør", "Søn"]
    forecast = []
    seen_dates = set()
    today = datetime.now().date()
    for entry in timeseries:
        entry_time = datetime.fromisoformat(entry["time"].replace("Z", "+00:00")).astimezone()
        entry_date = entry_time.date()
        if entry_date == today or entry_date in seen_dates:
            continue
        if entry_time.hour != 12:
            continue
        next_hours = entry["data"].get("next_6_hours") or entry["data"].get("next_1_hours", {})
        symbol_code = next_hours.get("summary", {}).get("symbol_code", "")
        if not symbol_code:
            continue
        instant = entry["data"]["instant"]["details"]
        forecast.append({
            "weekday": weekdays_no[entry_time.weekday()],
            "temperature": round(instant.get("air_temperature", 0.0), 1),
            "emoji": _symbol_to_emoji(symbol_code),
            "description": _symbol_to_description(symbol_code),
            "precipitation_mm": next_hours.get("details", {}).get("precipitation_amount", 0.0),
            "wind_speed": round(instant.get("wind_speed", 0.0), 1),
            "wind_gust": round(instant.get("wind_speed_of_gust", 0.0), 1),
            "wind_direction_compass": _degrees_to_compass(instant.get("wind_from_direction")),
        })
        seen_dates.add(entry_date)
        if len(forecast) >= days:
            break
    return forecast

TIMESTAMP_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
try:
    _timestamp_font = ImageFont.truetype(TIMESTAMP_FONT_PATH, 22)
except OSError:
    _timestamp_font = ImageFont.load_default()


def _with_timestamp_overlay(jpeg_bytes: bytes, captured_at: float) -> bytes:
    """Brenn inn dato/klokkeslett nederst til høyre på bildet."""
    try:
        image = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    except Exception:
        return jpeg_bytes

    text = datetime.fromtimestamp(captured_at).strftime("%d.%m.%Y %H:%M:%S")
    draw = ImageDraw.Draw(image)
    bbox = draw.textbbox((0, 0), text, font=_timestamp_font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    padding = 8
    x = image.width - text_w - padding * 2 - 10
    y = image.height - text_h - padding * 2 - 10

    overlay_box = [x, y, x + text_w + padding * 2, y + text_h + padding * 2]
    draw.rectangle(overlay_box, fill=(0, 0, 0, 160))
    draw.text((x + padding, y + padding - bbox[1]), text, font=_timestamp_font, fill=(255, 255, 255))

    out = io.BytesIO()
    image.save(out, format="JPEG", quality=90)
    return out.getvalue()

app = Flask(__name__)

PAGE_TEMPLATE = """
<!DOCTYPE html>
<html lang="no">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>🦆 Duck-Vision Live</title>
    <style>
        :root {
            color-scheme: dark;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: radial-gradient(circle at top, #1e2530 0%, #0c0f14 70%);
            color: #eef1f5;
            padding: 24px 16px 48px;
        }
        h1 {
            font-size: clamp(1.4rem, 4vw, 2rem);
            margin: 0 0 4px;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .subtitle {
            color: #8b95a5;
            font-size: 0.9rem;
            margin-bottom: 24px;
        }
        .stream-card {
            width: 100%;
            max-width: 900px;
            background: #151a22;
            border-radius: 18px;
            padding: 14px;
            box-shadow: 0 12px 40px rgba(0,0,0,0.45);
            border: 1px solid #232b38;
        }
        .stream-frame {
            position: relative;
            width: 100%;
            border-radius: 12px;
            overflow: hidden;
            background: #05070a;
            aspect-ratio: 16 / 9;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        #liveImg {
            width: 100%;
            height: 100%;
            object-fit: contain;
            display: block;
            cursor: zoom-in;
        }
        .stream-frame:fullscreen #liveImg,
        .stream-frame:-webkit-full-screen #liveImg {
            object-fit: contain;
            cursor: zoom-out;
            background: #000;
        }
        .stream-frame:fullscreen,
        .stream-frame:-webkit-full-screen {
            background: #000;
        }
        .stream-frame.pseudo-fullscreen {
            position: fixed;
            inset: 0;
            z-index: 9999;
            border-radius: 0;
            width: 100vw;
            height: 100vh;
            background: #000;
        }
        .stream-frame.pseudo-fullscreen #liveImg {
            cursor: zoom-out;
        }
        .badge-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: 12px;
            font-size: 0.85rem;
            color: #9aa4b5;
        }
        .live-dot {
            display: inline-block;
            width: 9px;
            height: 9px;
            border-radius: 50%;
            background: #35d07f;
            margin-right: 6px;
            box-shadow: 0 0 8px #35d07f;
            animation: pulse 1.6s infinite;
        }
        .live-dot.stale {
            background: #d9534f;
            box-shadow: 0 0 8px #d9534f;
            animation: none;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.35; }
        }
        select, button {
            background: #202836;
            border: 1px solid #2e3847;
            color: #eef1f5;
            border-radius: 8px;
            padding: 6px 10px;
            font-size: 0.85rem;
            cursor: pointer;
        }
        .controls {
            display: flex;
            gap: 8px;
            align-items: center;
        }
        footer {
            margin-top: 20px;
            color: #5b6474;
            font-size: 0.75rem;
            text-align: center;
        }
        .weather-card {
            width: 100%;
            max-width: 900px;
            margin-top: 16px;
            background: #151a22;
            border-radius: 18px;
            padding: 16px 20px;
            box-shadow: 0 12px 40px rgba(0,0,0,0.45);
            border: 1px solid #232b38;
            display: flex;
            align-items: center;
            gap: 18px;
            flex-wrap: wrap;
        }
        .weather-emoji {
            font-size: 2.6rem;
            line-height: 1;
        }
        .weather-main {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }
        .weather-location {
            font-size: 0.85rem;
            color: #8b95a5;
        }
        .weather-temp {
            font-size: 1.6rem;
            font-weight: 600;
        }
        .weather-details {
            display: flex;
            gap: 18px;
            margin-left: auto;
            font-size: 0.9rem;
            color: #c3cada;
            flex-wrap: wrap;
        }
        .weather-details span {
            display: flex;
            align-items: center;
            gap: 6px;
            white-space: nowrap;
        }
        .wind-arrow {
            display: inline-block;
            transition: transform 0.3s ease;
        }
        .forecast-row {
            width: 100%;
            display: flex;
            gap: 10px;
            overflow-x: auto;
            padding-top: 4px;
        }
        .forecast-item {
            flex: 0 0 auto;
            min-width: 64px;
            text-align: center;
            background: #1b222e;
            border-radius: 10px;
            padding: 8px 10px;
            font-size: 0.8rem;
            color: #c3cada;
        }
        .forecast-item .fc-label {
            color: #8b95a5;
            font-size: 0.72rem;
            margin-bottom: 4px;
        }
        .forecast-item .fc-emoji {
            font-size: 1.4rem;
        }
        .forecast-item .fc-temp {
            font-weight: 600;
            margin-top: 2px;
        }
        .forecast-section {
            width: 100%;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #232b38;
        }
        .forecast-section h3 {
            margin: 0 0 8px;
            font-size: 0.78rem;
            color: #8b95a5;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.04em;
        }
        .weather-main, .forecast-item {
            cursor: pointer;
        }
        .modal-overlay {
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(5, 7, 10, 0.75);
            z-index: 10000;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        .modal-overlay.open {
            display: flex;
        }
        .modal-box {
            background: #151a22;
            border: 1px solid #232b38;
            border-radius: 16px;
            padding: 24px;
            max-width: 360px;
            width: 100%;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
            text-align: center;
        }
        .modal-emoji {
            font-size: 3.2rem;
        }
        .modal-title {
            font-size: 1.1rem;
            font-weight: 600;
            margin: 8px 0 2px;
        }
        .modal-subtitle {
            color: #8b95a5;
            font-size: 0.85rem;
            margin-bottom: 16px;
        }
        .modal-description {
            color: #c3cada;
            font-size: 0.88rem;
            line-height: 1.4;
            margin: -8px 0 16px;
        }
        .modal-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            text-align: left;
        }
        .modal-grid div {
            background: #1b222e;
            border-radius: 10px;
            padding: 8px 10px;
            font-size: 0.85rem;
            color: #c3cada;
        }
        .modal-grid .label {
            display: block;
            color: #8b95a5;
            font-size: 0.72rem;
            margin-bottom: 2px;
        }
        .modal-close {
            margin-top: 18px;
            background: #202836;
            border: 1px solid #2e3847;
            color: #eef1f5;
            border-radius: 8px;
            padding: 8px 16px;
            font-size: 0.85rem;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <h1>🦆 Duck-Vision Live</h1>
    <div class="subtitle">Siste bilde fra kameraet, oppdateres automatisk</div>

    <div class="stream-card">
        <div class="stream-frame" id="streamFrame">
            <img id="liveImg" src="/stream.mjpg" alt="Live kamera" title="Klikk for fullskjerm">
        </div>
        <div class="badge-row">
            <span><span class="live-dot" id="liveDot"></span><span id="statusText">Kobler til...</span></span>
            <div class="controls">
                <label for="refreshRate">Oppdatering:</label>
                <select id="refreshRate">
                    <option value="300">Rask (0.3s)</option>
                    <option value="1000" selected>Normal (1s)</option>
                    <option value="3000">Sakte (3s)</option>
                </select>
            </div>
        </div>
    </div>

    <footer>Duck-Vision Live Stream · oppdatert {{ started_at }}</footer>

    <div class="weather-card" id="weatherCard">
        <span class="weather-emoji" id="weatherEmoji">…</span>
        <div class="weather-main">
            <span class="weather-location">Vær på Åmot, Sokndal</span>
            <span class="weather-temp" id="weatherTemp">--°</span>
        </div>
        <div class="weather-details">
            <span>💨 <span id="weatherWind">--</span> m/s <span class="wind-arrow" id="windArrow">↑</span> <span id="windCompass">--</span></span>
            <span>💨💨 kast <span id="weatherGust">--</span> m/s</span>
            <span>🌧️ <span id="weatherRain">--</span> <span id="weatherRainUnit">mm</span></span>
            <span id="weatherUpdated">--</span>
        </div>
        <div class="forecast-section">
            <h3>Neste timer</h3>
            <div class="forecast-row" id="hourlyForecast"></div>
        </div>
        <div class="forecast-section">
            <h3>Neste dager</h3>
            <div class="forecast-row" id="dailyForecast"></div>
        </div>
    </div>

    <div class="modal-overlay" id="weatherModal">
        <div class="modal-box">
            <div class="modal-emoji" id="modalEmoji">🌡️</div>
            <div class="modal-title" id="modalTitle">--</div>
            <div class="modal-subtitle" id="modalSubtitle">--</div>
            <div class="modal-description" id="modalDescription">--</div>
            <div class="modal-grid">
                <div><span class="label">Temperatur</span><span id="modalTemp">--</span></div>
                <div><span class="label">Vind</span><span id="modalWind">--</span></div>
                <div><span class="label">Vindkast</span><span id="modalGust">--</span></div>
                <div><span class="label">Nedbør</span><span id="modalRain">--</span></div>
            </div>
            <button class="modal-close" id="modalCloseBtn">Lukk</button>
        </div>
    </div>

    <script>
        const img = document.getElementById('liveImg');
        const statusText = document.getElementById('statusText');
        const liveDot = document.getElementById('liveDot');
        const refreshRate = document.getElementById('refreshRate');
        const streamFrame = document.getElementById('streamFrame');

        function isFullscreen() {
            return document.fullscreenElement || document.webkitFullscreenElement || streamFrame.classList.contains('pseudo-fullscreen');
        }

        streamFrame.addEventListener('click', () => {
            const request = streamFrame.requestFullscreen || streamFrame.webkitRequestFullscreen;
            if (!request) {
                // iOS Safari has no Fullscreen API for images; fake it with CSS instead.
                streamFrame.classList.toggle('pseudo-fullscreen');
                return;
            }
            if (isFullscreen()) {
                (document.exitFullscreen || document.webkitExitFullscreen).call(document);
            } else {
                request.call(streamFrame);
            }
        });

        let lastLoadTime = Date.now();
        let timer = null;

        function refreshImage() {
            const url = '/frame.jpg?t=' + Date.now();
            const probe = new Image();
            probe.onload = () => {
                img.src = url;
                lastLoadTime = Date.now();
                statusText.textContent = 'Live';
                liveDot.classList.remove('stale');
            };
            probe.onerror = () => {
                statusText.textContent = 'Ingen forbindelse med kameraet';
                liveDot.classList.add('stale');
            };
            probe.src = url;
        }

        function scheduleRefresh() {
            if (timer) clearInterval(timer);
            timer = setInterval(refreshImage, parseInt(refreshRate.value, 10));
        }

        refreshRate.addEventListener('change', scheduleRefresh);
        refreshImage();
        scheduleRefresh();

        setInterval(() => {
            if (Date.now() - lastLoadTime > 8000) {
                statusText.textContent = 'Bildet er gammelt (kamera kan være nede)';
                liveDot.classList.add('stale');
            }
        }, 2000);

        function refreshWeather() {
            fetch('/weather.json')
                .then(r => r.json())
                .then(w => {
                    if (w.error) return;
                    document.getElementById('weatherEmoji').textContent = w.emoji;
                    document.getElementById('weatherTemp').textContent = w.temperature.toFixed(1) + '°C';
                    document.getElementById('weatherWind').textContent = w.wind_speed.toFixed(1);
                    document.getElementById('weatherGust').textContent = w.wind_gust.toFixed(1);
                    document.getElementById('weatherRain').textContent = w.precipitation_mm.toFixed(1);
                    document.getElementById('weatherRainUnit').textContent = w.precipitation_is_now ? 'mm/t (nå)' : 'mm';
                    document.getElementById('weatherUpdated').textContent = 'oppdatert ' + w.updated_at;
                    document.getElementById('windCompass').textContent = w.wind_direction_compass;
                    if (w.wind_direction !== null && w.wind_direction !== undefined) {
                        // Pilen peker dit vinden blåser MOT (motsatt av "from direction")
                        document.getElementById('windArrow').style.transform = `rotate(${w.wind_direction + 180}deg)`;
                    }

                    const nowItem = {
                        title: 'Nå',
                        subtitle: 'oppdatert ' + w.updated_at,
                        emoji: w.emoji,
                        description: w.description,
                        longDescription: w.long_description,
                        temperature: w.temperature,
                        wind_speed: w.wind_speed,
                        wind_gust: w.wind_gust,
                        wind_direction_compass: w.wind_direction_compass,
                        precipitation_mm: w.precipitation_mm,
                        precipitation_is_now: w.precipitation_is_now,
                    };
                    document.getElementById('weatherCard').querySelector('.weather-main').onclick = () => openWeatherModal(nowItem);

                    const hourlyEl = document.getElementById('hourlyForecast');
                    hourlyEl.innerHTML = '';
                    (w.hourly || []).forEach(h => {
                        const el = document.createElement('div');
                        el.className = 'forecast-item';
                        el.innerHTML = `
                            <div class="fc-label">${h.time}</div>
                            <div class="fc-emoji">${h.emoji}</div>
                            <div class="fc-temp">${h.temperature.toFixed(0)}°</div>
                        `;
                        el.onclick = () => openWeatherModal({
                            title: h.time,
                            subtitle: 'Prognose',
                            emoji: h.emoji,
                            description: h.description,
                            longDescription: `${h.description}. Vind ${h.wind_speed.toFixed(1)} m/s fra ${h.wind_direction_compass}.`,
                            temperature: h.temperature,
                            wind_speed: h.wind_speed,
                            wind_gust: h.wind_gust,
                            wind_direction_compass: h.wind_direction_compass,
                            precipitation_mm: h.precipitation_mm,
                            precipitation_is_now: false,
                        });
                        hourlyEl.appendChild(el);
                    });

                    const dailyEl = document.getElementById('dailyForecast');
                    dailyEl.innerHTML = '';
                    (w.daily || []).forEach(d => {
                        const el = document.createElement('div');
                        el.className = 'forecast-item';
                        el.innerHTML = `
                            <div class="fc-label">${d.weekday}</div>
                            <div class="fc-emoji">${d.emoji}</div>
                            <div class="fc-temp">${d.temperature.toFixed(0)}°</div>
                        `;
                        el.onclick = () => openWeatherModal({
                            title: d.weekday,
                            subtitle: 'Prognose rundt kl 12',
                            emoji: d.emoji,
                            description: d.description,
                            longDescription: `${d.description}. Vind ${d.wind_speed.toFixed(1)} m/s fra ${d.wind_direction_compass}.`,
                            temperature: d.temperature,
                            wind_speed: d.wind_speed,
                            wind_gust: d.wind_gust,
                            wind_direction_compass: d.wind_direction_compass,
                            precipitation_mm: d.precipitation_mm,
                            precipitation_is_now: false,
                        });
                        dailyEl.appendChild(el);
                    });
                })
                .catch(() => {});
        }

        const weatherModal = document.getElementById('weatherModal');

        function openWeatherModal(item) {
            document.getElementById('modalEmoji').textContent = item.emoji;
            document.getElementById('modalTitle').textContent = item.title;
            document.getElementById('modalSubtitle').textContent = item.subtitle;
            document.getElementById('modalDescription').textContent = item.longDescription || item.description;
            document.getElementById('modalTemp').textContent = item.temperature.toFixed(1) + '°C';
            document.getElementById('modalWind').textContent = `${item.wind_speed.toFixed(1)} m/s ${item.wind_direction_compass || ''}`;
            document.getElementById('modalGust').textContent = item.wind_gust.toFixed(1) + ' m/s';
            document.getElementById('modalRain').textContent = item.precipitation_mm.toFixed(1) + (item.precipitation_is_now ? ' mm/t (nå)' : ' mm');
            weatherModal.classList.add('open');
        }

        function closeWeatherModal() {
            weatherModal.classList.remove('open');
        }

        document.getElementById('modalCloseBtn').addEventListener('click', closeWeatherModal);
        weatherModal.addEventListener('click', (e) => {
            if (e.target === weatherModal) closeWeatherModal();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeWeatherModal();
        });

        refreshWeather();
        setInterval(refreshWeather, 10 * 60 * 1000);
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE_TEMPLATE, started_at=time.strftime("%H:%M:%S"))


@app.route("/frame.jpg")
def frame():
    """Returner siste kameraframe som ren JPEG (pollet av frontend), med dato/klokkeslett brent inn."""
    if not LIVE_IMAGE_PATH.exists():
        return Response(status=404)

    try:
        data = LIVE_IMAGE_PATH.read_bytes()
        captured_at = LIVE_IMAGE_PATH.stat().st_mtime
    except OSError:
        return Response(status=503)

    data = _with_timestamp_overlay(data, captured_at)

    resp = Response(data, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


@app.route("/stream.mjpg")
def stream_placeholder():
    """Initielt bilde for <img>-taggen før JS overtar pollingen."""
    return frame()


@app.route("/weather.json")
def weather():
    try:
        return jsonify(_fetch_weather())
    except Exception as e:
        return jsonify({"error": str(e)}), 503


if __name__ == "__main__":
    import os

    port = int(os.environ.get("LIVE_STREAM_PORT", "8091"))
    print(f"🦆 Duck-Vision Live Stream kjører på http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
