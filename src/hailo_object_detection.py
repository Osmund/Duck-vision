"""
Hailo Object Detection - on-demand objektdeteksjon via AI HAT+.

Implementasjon:
  - bruker rpicam-vid + Hailo postprocess stage (hailo_yolo_inference)
  - leser deteksjoner via object_detect_udp
  - returnerer samme format som IMX500-detektoren:
      (norsk_navn, confidence, (y1, x1, y2, x2))
"""

from __future__ import annotations

import json
import logging
import os
import re
import socket
import subprocess
import tempfile
import time
from typing import Dict, List, Tuple

try:
    from .imx500_object_detection import COCO_CLASSES_NO
except Exception:
    from imx500_object_detection import COCO_CLASSES_NO

logger = logging.getLogger(__name__)


# COCO-80 klassenavn i standard rekkefolge (engelsk)
COCO_CLASSES_EN = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat", "traffic light",
    "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep", "cow",
    "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee",
    "skis", "snowboard", "sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
    "tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair", "couch",
    "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse", "remote", "keyboard",
    "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase", "scissors",
    "teddy bear", "hair drier", "toothbrush",
]

EN_TO_NO = {name: COCO_CLASSES_NO[idx] for idx, name in enumerate(COCO_CLASSES_EN) if idx in COCO_CLASSES_NO}


class HailoObjectDetector:
    """On-demand Hailo deteksjon for object mode i DuckVision."""

    def __init__(
        self,
        confidence_threshold: float = 0.35,
        duration_ms: int = 1800,
        width: int = 1280,
        height: int = 720,
        fps: int = 15,
    ):
        self.confidence_threshold = confidence_threshold
        self.duration_ms = duration_ms
        self.width = width
        self.height = height
        self.fps = fps
        self.last_detections: List[Tuple[str, float, Tuple[float, float, float, float]]] = []

        logger.info(
            "HailoObjectDetector initialisert (thr=%.2f, %dx%d@%dfps, %dms)",
            self.confidence_threshold,
            self.width,
            self.height,
            self.fps,
            self.duration_ms,
        )

    def start(self):
        """Ingen vedvarende ressurs a starte; beholdt for API-likhet."""
        return

    def stop(self):
        """Ingen vedvarende ressurs a stoppe; beholdt for API-likhet."""
        return

    def _build_postprocess_config(self, ip: str, port: int) -> str:
        cfg = {
            "rpicam-apps": {
                "lores": {
                    "width": 640,
                    "height": 640,
                    "format": "rgb",
                }
            },
            "hailo_yolo_inference": {
                "hef_file_8L": "/usr/share/hailo-models/yolov8s_h8l.hef",
                "hef_file_8": "/usr/share/hailo-models/yolov8s_h8.hef",
                "max_detections": 20,
                "threshold": self.confidence_threshold,
            },
            "object_detect_udp": {
                "ip": ip,
                "port": port,
            },
        }

        fd, path = tempfile.mkstemp(suffix=".json", prefix="hailo_pp_")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
        return path

    @staticmethod
    def _parse_packet_labels(packet: bytes) -> List[str]:
        # Pakker inneholder binardata + klasse-navn i klartekst.
        text = packet.decode("latin1", errors="ignore")
        text = re.sub(r"[^A-Za-z ]+", " ", text).lower()
        found = []
        for label in COCO_CLASSES_EN:
            if re.search(rf"\b{re.escape(label)}\b", text):
                found.append(label)
        return found

    def detect_objects(self) -> List[Tuple[str, float, Tuple[float, float, float, float]]]:
        """Kjor kort Hailo-pass og returner detekterte objektnavn."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("127.0.0.1", 0))
        sock.settimeout(0.20)
        ip, port = sock.getsockname()

        pp_path = self._build_postprocess_config(ip, port)
        video_out = tempfile.NamedTemporaryFile(suffix=".h264", delete=False)
        video_out_path = video_out.name
        video_out.close()

        cmd = [
            "rpicam-vid",
            "-t",
            str(self.duration_ms),
            "-n",
            "--width",
            str(self.width),
            "--height",
            str(self.height),
            "--framerate",
            str(self.fps),
            "--post-process-file",
            pp_path,
            "-o",
            video_out_path,
        ]

        label_counts: Dict[str, int] = {}
        packets_seen = 0
        start = time.time()
        proc = None

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
            end_time = start + (self.duration_ms / 1000.0) + 1.2

            while time.time() < end_time:
                try:
                    data, _ = sock.recvfrom(65535)
                    packets_seen += 1
                    for label in self._parse_packet_labels(data):
                        label_counts[label] = label_counts.get(label, 0) + 1
                except socket.timeout:
                    continue

            stderr = ""
            if proc is not None:
                _, stderr = proc.communicate(timeout=8)
                if proc.returncode not in (0,):
                    logger.warning("Hailo rpicam-vid returnerte kode %s", proc.returncode)
                    if stderr:
                        logger.warning("Hailo stderr tail: %s", " | ".join(stderr.splitlines()[-4:]))

            detections = []
            for label, count in sorted(label_counts.items(), key=lambda kv: kv[1], reverse=True):
                # UDP payload mangler stabil confidence; bruk konservativ score basert pa persistens.
                confidence = min(0.95, 0.45 + 0.05 * count)
                no_name = EN_TO_NO.get(label, label)
                detections.append((no_name, float(confidence), (0.0, 0.0, 1.0, 1.0)))

            self.last_detections = detections

            elapsed = (time.time() - start) * 1000.0
            logger.info(
                "Hailo detect ferdig: %d pakker, %d labels, %.0fms",
                packets_seen,
                len(detections),
                elapsed,
            )
            return detections

        except Exception as e:
            logger.error("Feil ved Hailo object detection: %s", e)
            return []
        finally:
            if proc is not None and proc.poll() is None:
                proc.kill()
            sock.close()
            try:
                os.unlink(pp_path)
            except Exception:
                pass
            try:
                os.unlink(video_out_path)
            except Exception:
                pass
