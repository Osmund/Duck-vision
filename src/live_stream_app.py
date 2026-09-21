"""
Duck-Vision Live Stream - Flask-app som viser duck_vision_live.jpg som en enkel
"stream" via auto-refresh, pluss litt statusinfo fra MQTT-status-filen om den finnes.

Kjør: .venv/bin/python3 src/live_stream_app.py
Standard port: 8090
"""

from __future__ import annotations

import time
from pathlib import Path

from flask import Flask, Response, render_template_string

BASE_DIR = Path(__file__).resolve().parents[1]
LIVE_IMAGE_PATH = BASE_DIR / "data" / "logs" / "duck_vision_live.jpg"

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

    <script>
        const img = document.getElementById('liveImg');
        const statusText = document.getElementById('statusText');
        const liveDot = document.getElementById('liveDot');
        const refreshRate = document.getElementById('refreshRate');
        const streamFrame = document.getElementById('streamFrame');

        function isFullscreen() {
            return document.fullscreenElement || document.webkitFullscreenElement;
        }

        streamFrame.addEventListener('click', () => {
            if (isFullscreen()) {
                (document.exitFullscreen || document.webkitExitFullscreen).call(document);
            } else {
                const request = streamFrame.requestFullscreen || streamFrame.webkitRequestFullscreen;
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
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(PAGE_TEMPLATE, started_at=time.strftime("%H:%M:%S"))


@app.route("/frame.jpg")
def frame():
    """Returner siste kameraframe som ren JPEG (pollet av frontend)."""
    if not LIVE_IMAGE_PATH.exists():
        return Response(status=404)

    try:
        data = LIVE_IMAGE_PATH.read_bytes()
    except OSError:
        return Response(status=503)

    resp = Response(data, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


@app.route("/stream.mjpg")
def stream_placeholder():
    """Initielt bilde for <img>-taggen før JS overtar pollingen."""
    return frame()


if __name__ == "__main__":
    import os

    port = int(os.environ.get("LIVE_STREAM_PORT", "8091"))
    print(f"🦆 Duck-Vision Live Stream kjører på http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, threaded=True)
