# Vision Web Dashboard

This dashboard gives a mobile-friendly view of what Duck-Vision is detecting right now.

## What it shows

- Live MQTT event stream from `duck/vision/*`
- Last event payload
- Last object/face events
- Latest OpenAI snapshot image from `data/logs/openai_vision_debug.jpg`
- Live low-latency preview image from `data/logs/duck_vision_live.jpg`

## Run manually

From the project root:

```bash
.venv/bin/python src/vision_web.py
```

Then open:

```text
http://<vision-pi-ip>:8090
```

## Optional: run as systemd service

Install service file:

```bash
sudo cp duck-vision-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now duck-vision-web
sudo systemctl status duck-vision-web
```

## API endpoints

- `GET /` dashboard UI
- `GET /health` health check
- `GET /api/state` JSON state
- `GET /snapshot.jpg` latest OpenAI snapshot (if available)
- `POST /api/command` publish command to `duck/samantha/commands`

Example command:

```bash
curl -X POST http://localhost:8090/api/command \
  -H 'content-type: application/json' \
  -d '{"command":"analyze_scene","question":"Hva ser du akkurat naa?"}'
```

## Notes

- Snapshot is updated when `analyze_scene` is used.
- Live preview is continuously refreshed by `duck-vision` while it runs.
- This first version focuses on reliable event visibility from mobile.
- Full live video stream with overlays can be added in a next step.

## Live preview tuning

Set these env vars for `duck-vision` if needed:

- `VISION_WEB_PREVIEW_ENABLED=true|false`
- `VISION_WEB_PREVIEW_INTERVAL=0.7` (seconds between frame exports)
- `VISION_WEB_PREVIEW_MAX_WIDTH=960`
- `VISION_WEB_PREVIEW_PATH=/home/admog/Code/Duck-vision/data/logs/duck_vision_live.jpg`
