#!/usr/bin/env python3
"""
Duck-Vision Web Dashboard

Lightweight mobile-friendly web UI that shows:
- live detection/event state from MQTT
- latest OpenAI snapshot image (if available)
- quick action buttons for detect/analyze commands
"""

import json
import os
import threading
import time
import io
from collections import deque
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import paho.mqtt.client as mqtt
from PIL import Image

from config import MQTT_CONFIG, TOPICS


HOST = os.getenv("VISION_WEB_HOST", "0.0.0.0")
PORT = int(os.getenv("VISION_WEB_PORT", "8090"))
MAX_EVENTS = int(os.getenv("VISION_WEB_MAX_EVENTS", "80"))
BASE_DIR = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT_PATH = BASE_DIR / "data" / "logs" / "openai_vision_debug.jpg"
DEFAULT_LIVE_PATH = BASE_DIR / "data" / "logs" / "duck_vision_live.jpg"
SNAPSHOT_PATH = Path(os.getenv("VISION_WEB_SNAPSHOT_PATH", str(DEFAULT_SNAPSHOT_PATH)))
LIVE_PATH = Path(os.getenv("VISION_WEB_PREVIEW_PATH", str(DEFAULT_LIVE_PATH)))
SNAPSHOT_MAX_WIDTH = max(320, int(os.getenv("VISION_WEB_SNAPSHOT_MAX_WIDTH", "960")))
SNAPSHOT_MAX_HEIGHT = max(240, int(os.getenv("VISION_WEB_SNAPSHOT_MAX_HEIGHT", "720")))
SNAPSHOT_QUALITY = max(45, min(90, int(os.getenv("VISION_WEB_SNAPSHOT_QUALITY", "72"))))


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class SharedState:
    def __init__(self):
        self.lock = threading.Lock()
        self.started_at = now_iso()
        self.vision_status = "unknown"
        self.last_object = None
        self.last_face = None
        self.last_event = None
        self.last_command = None
        self.events = deque(maxlen=MAX_EVENTS)

    def add_event(self, topic: str, payload):
        with self.lock:
            evt = {
                "ts": time.time(),
                "topic": topic,
                "payload": payload,
            }
            self.events.appendleft(evt)
            self.last_event = evt

            if topic == TOPICS.get("object_detected"):
                self.last_object = payload
            elif topic == TOPICS.get("face_detected"):
                self.last_face = payload
            elif topic == "duck/vision/status":
                if isinstance(payload, dict):
                    self.vision_status = payload.get("status", "unknown")

    def set_last_command(self, command_payload):
        with self.lock:
            self.last_command = {
                "ts": time.time(),
                "payload": command_payload,
            }

    def snapshot(self):
        with self.lock:
            return {
                "started_at": self.started_at,
                "vision_status": self.vision_status,
                "last_object": self.last_object,
                "last_face": self.last_face,
                "last_event": self.last_event,
                "last_command": self.last_command,
                "events": list(self.events),
            }


STATE = SharedState()


class DashboardMQTT:
    def __init__(self):
        self.client = mqtt.Client(client_id="duck-vision-web")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        if MQTT_CONFIG["username"]:
            self.client.username_pw_set(MQTT_CONFIG["username"], MQTT_CONFIG["password"])

    def connect(self):
        self.client.connect(MQTT_CONFIG["broker"], MQTT_CONFIG["port"], keepalive=60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        if rc != 0:
            print(f"[vision-web] MQTT connect failed: rc={rc}")
            return
        print("[vision-web] MQTT connected")
        topics = [
            "duck/vision/status",
            TOPICS.get("vision_to_samantha", "duck/vision/events"),
            TOPICS.get("object_detected", "duck/vision/object"),
            TOPICS.get("face_detected", "duck/vision/face"),
        ]
        for topic in topics:
            self.client.subscribe(topic)

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8", errors="ignore"))
        except Exception:
            payload = {"raw": msg.payload.decode("utf-8", errors="ignore")}
        STATE.add_event(msg.topic, payload)

    def publish_command(self, payload: dict):
        self.client.publish(TOPICS["samantha_to_vision"], json.dumps(payload, ensure_ascii=False), qos=1)
        STATE.set_last_command(payload)


MQTT_BRIDGE = DashboardMQTT()


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Duck Vision Dashboard</title>
  <style>
    :root {
      --bg: #f0efe8;
      --card: #fffdf7;
      --text: #132025;
      --muted: #5d6f76;
      --brand: #006b59;
      --brand-2: #f4a300;
      --border: #d8d2c3;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      color: var(--text);
      background: radial-gradient(circle at 10% 0%, #fff8de, var(--bg) 55%);
    }
    .wrap { max-width: 960px; margin: 0 auto; padding: 16px; }
    .title { font-size: 1.3rem; font-weight: 700; margin: 4px 0 12px; }
    .grid { display: grid; gap: 12px; grid-template-columns: 1fr; }
    .grid > .card { min-width: 0; }
    .card {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 12px;
      box-shadow: 0 6px 20px rgba(0,0,0,0.05);
    }
    .muted { color: var(--muted); font-size: 0.92rem; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; }
    .live-wrap { position: relative; }
    .overlay {
      position: absolute;
      left: 8px;
      bottom: 8px;
      background: rgba(0, 0, 0, 0.64);
      color: #d8ffea;
      border-radius: 8px;
      padding: 6px 8px;
      font-size: 0.82rem;
      max-width: calc(100% - 16px);
      backdrop-filter: blur(2px);
    }
    button {
      border: 1px solid var(--border);
      background: white;
      color: var(--text);
      border-radius: 10px;
      padding: 8px 10px;
      font-size: 0.92rem;
      cursor: pointer;
    }
    button.primary { background: var(--brand); color: white; border-color: var(--brand); }
    button.warn { background: var(--brand-2); color: #1f1300; border-color: var(--brand-2); }
    img { max-width: 100%; border-radius: 10px; border: 1px solid var(--border); }
    #snap {
      display: block;
      width: 100%;
      max-height: 28vh;
      object-fit: contain;
      background: #0f1417;
    }
    #liveCanvas {
      display: block;
      width: 100%;
      max-height: 42vh;
      object-fit: contain;
      background: #0f1417;
      border-radius: 10px;
      border: 1px solid var(--border);
    }
    pre {
      background: #11181b;
      color: #d4efef;
      border-radius: 10px;
      padding: 10px;
      font-size: 0.74rem;
      overflow: auto;
      max-height: 180px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      word-break: break-word;
    }
    @media (min-width: 880px) {
      .grid { grid-template-columns: 1.1fr 1fr; }
      #snap { max-height: 34vh; }
      .events-card { grid-column: 1 / -1; }
    }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="title">Duck Vision Dashboard</div>
    <div class="grid">
      <section class="card">
        <div><strong>Status:</strong> <span id="status">...</span></div>
        <div class="muted" id="uptime"></div>
        <div class="row">
          <button class="primary" onclick="sendCmd('detect_object')">Detect Object</button>
          <button onclick="sendCmd('check_person')">Check Person</button>
          <button class="warn" onclick="askInspect()">Inspect Scene</button>
        </div>
        <div class="muted" id="lastcmd"></div>
      </section>
      <section class="card">
        <div><strong>Live Camera</strong></div>
        <div class="muted">Low-latency preview from current camera view.</div>
        <div class="live-wrap">
          <canvas id="liveCanvas" aria-label="Live preview"></canvas>
          <div class="overlay" id="overlay">Waiting for detections...</div>
        </div>
      </section>
      <section class="card">
        <div><strong>Latest Snapshot</strong></div>
        <div class="muted">Updates when OpenAI scene analysis is run.</div>
        <img id="snap" alt="Latest snapshot" src="/snapshot.jpg" />
      </section>
      <section class="card">
        <div><strong>Latest Event</strong></div>
        <pre id="latest">{}</pre>
      </section>
      <section class="card events-card">
        <div><strong>Recent Events</strong></div>
        <pre id="events">[]</pre>
      </section>
    </div>
  </div>

  <script>
    const liveCanvas = document.getElementById('liveCanvas');
    const liveCtx = liveCanvas.getContext('2d');

    function clamp(v, min, max) {
      return Math.max(min, Math.min(max, v));
    }

    function drawDetections(lastObject, frameW, frameH) {
      if (!lastObject) return;

      const objects = (Array.isArray(lastObject.all_objects) && lastObject.all_objects.length)
        ? lastObject.all_objects
        : [lastObject];

      liveCtx.lineWidth = Math.max(2, Math.round(frameW / 260));
      liveCtx.font = `${Math.max(12, Math.round(frameW / 48))}px IBM Plex Sans, Segoe UI, sans-serif`;

      objects.forEach((obj) => {
        if (!obj || !Array.isArray(obj.bbox) || obj.bbox.length < 4) return;

        const b = obj.bbox.map(Number);
        const normalized = b.every((n) => Number.isFinite(n) && n >= 0 && n <= 1.2);

        let x1 = b[0], y1 = b[1], x2 = b[2], y2 = b[3];
        if (normalized) {
          x1 *= frameW;
          x2 *= frameW;
          y1 *= frameH;
          y2 *= frameH;
        }

        x1 = clamp(x1, 0, frameW);
        x2 = clamp(x2, 0, frameW);
        y1 = clamp(y1, 0, frameH);
        y2 = clamp(y2, 0, frameH);

        const w = Math.max(2, x2 - x1);
        const h = Math.max(2, y2 - y1);
        const areaRatio = (w * h) / (frameW * frameH);

        // Some detections can be coarse fallback boxes that cover almost the whole frame.
        // Do not draw those as overlays, they make the preview look fully tinted.
        if (areaRatio > 0.92) return;

        const label = `${obj.name || obj.object_name || 'object'} ${Math.round((obj.confidence || 0) * 100)}%`;

        liveCtx.strokeStyle = '#38f2a3';
        liveCtx.strokeRect(x1, y1, w, h);

        const textW = liveCtx.measureText(label).width;
        const textPad = 4;
        const textH = Math.max(14, Math.round(frameW / 42));
        const textX = x1;
        const textY = Math.max(0, y1 - textH - 2);

        liveCtx.fillStyle = 'rgba(0, 0, 0, 0.65)';
        liveCtx.fillRect(textX, textY, textW + textPad * 2, textH);
        liveCtx.fillStyle = '#e9fff6';
        liveCtx.fillText(label, textX + textPad, textY + textH - 5);
      });
    }

    function refreshLiveFrame(lastObject) {
      const img = new Image();
      img.onload = () => {
        const frameW = img.naturalWidth || img.width;
        const frameH = img.naturalHeight || img.height;
        if (!frameW || !frameH) return;

        liveCanvas.width = frameW;
        liveCanvas.height = frameH;
        liveCtx.drawImage(img, 0, 0, frameW, frameH);
        drawDetections(lastObject, frameW, frameH);
      };
      img.src = '/live.jpg?t=' + Date.now();
    }

    async function loadState() {
      const res = await fetch('/api/state');
      const data = await res.json();
      const summarizePayload = (payload) => {
        try {
          const text = JSON.stringify(payload);
          if (!text) return '';
          return text.length > 180 ? (text.slice(0, 180) + ' ...') : text;
        } catch (_) {
          return String(payload);
        }
      };

      document.getElementById('status').textContent = data.vision_status;
      document.getElementById('uptime').textContent = 'Web started: ' + data.started_at;
      document.getElementById('latest').textContent = JSON.stringify(data.last_event || {}, null, 2);
      document.getElementById('events').textContent = (data.events || [])
        .slice(0, 12)
        .map((evt) => {
          const stamp = evt.ts ? new Date(evt.ts * 1000).toLocaleTimeString() : '--:--:--';
          return `${stamp}  ${evt.topic || 'unknown'}\\n${summarizePayload(evt.payload)}`;
        })
        .join('\\n\\n');
      document.getElementById('lastcmd').textContent = data.last_command ? ('Last command: ' + JSON.stringify(data.last_command.payload)) : '';
      const o = data.last_object || {};
      const overlay = o.object_name ? (`Object: ${o.object_name} (${Math.round((o.confidence || 0) * 100)}%)`) : 'No recent object detection';
      document.getElementById('overlay').textContent = overlay;
      refreshLiveFrame(o);
      document.getElementById('snap').src = '/snapshot.jpg?t=' + Date.now();
    }

    async function sendCmd(command, question) {
      const body = { command };
      if (question) body.question = question;
      await fetch('/api/command', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body)
      });
      setTimeout(loadState, 350);
    }

    function askInspect() {
      const q = prompt('Question for scene inspection:', 'Hvem er i bildet, og hva skjer akkurat naa?');
      if (q) sendCmd('inspect_scene', q);
    }

    loadState();
    setInterval(loadState, 900);
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    server_version = "DuckVisionWeb/0.1"

    def _send_jpeg_file(self, path: Path, max_width: int = None, max_height: int = None, quality: int = 72):
        try:
            data = path.read_bytes()
            if max_width or max_height:
                with Image.open(io.BytesIO(data)) as im:
                    w, h = im.size
                    target_w = max_width or w
                    target_h = max_height or h
                    if w > target_w or h > target_h:
                        im.thumbnail((target_w, target_h))
                    out = io.BytesIO()
                    im.save(out, format="JPEG", quality=quality, optimize=True)
                    data = out.getvalue()

            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        except Exception as e:
            return self._send_json(500, {"error": str(e)})

    def _send_json(self, code: int, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _send_text(self, code: int, text: str, ctype: str = "text/plain; charset=utf-8"):
        payload = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            return self._send_text(200, HTML, "text/html; charset=utf-8")

        if path == "/health":
            return self._send_json(200, {"ok": True, "time": now_iso()})

        if path == "/api/state":
            return self._send_json(200, STATE.snapshot())

        if path == "/snapshot.jpg":
            if not SNAPSHOT_PATH.exists():
                return self._send_json(404, {"error": f"snapshot not found: {SNAPSHOT_PATH}"})
            return self._send_jpeg_file(
            SNAPSHOT_PATH,
            max_width=SNAPSHOT_MAX_WIDTH,
            max_height=SNAPSHOT_MAX_HEIGHT,
            quality=SNAPSHOT_QUALITY,
            )

        if path == "/live.jpg":
            target = LIVE_PATH if LIVE_PATH.exists() else SNAPSHOT_PATH
            if not target.exists():
                return self._send_json(404, {"error": f"preview not found: {LIVE_PATH}"})
            return self._send_jpeg_file(target)

        if path == "/api/command":
            qs = parse_qs(parsed.query)
            cmd = (qs.get("cmd") or [""])[0]
            question = (qs.get("question") or [None])[0]
            if not cmd:
                return self._send_json(400, {"error": "missing cmd"})
            payload = {"command": cmd}
            if question:
                payload["question"] = question
            MQTT_BRIDGE.publish_command(payload)
            return self._send_json(200, {"ok": True, "published": payload})

        return self._send_json(404, {"error": "not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/api/command":
            return self._send_json(404, {"error": "not found"})

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            return self._send_json(400, {"error": "invalid json"})

        command = payload.get("command")
        if not command:
            return self._send_json(400, {"error": "missing command"})

        outbound = {"command": command}
        if payload.get("question"):
            outbound["question"] = payload["question"]

        MQTT_BRIDGE.publish_command(outbound)
        return self._send_json(200, {"ok": True, "published": outbound})

    def log_message(self, format, *args):
        return


def main():
    print(f"[vision-web] Starting MQTT bridge to {MQTT_CONFIG['broker']}:{MQTT_CONFIG['port']}")
    MQTT_BRIDGE.connect()

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[vision-web] Dashboard listening on http://{HOST}:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
