# AI-Powered Driver Assistance System (ADAS)

This repository contains an integrated Advanced Driver Assistance System combining driver monitoring (drowsiness and behavioral analysis) and forward-view road perception (traffic sign recognition and lane/turn detection). The project targets Raspberry Pi 5 for edge deployment and supports a desktop test mode.

**Main features**
- Driver drowsiness detection: EAR, MAR, yawning counter, head-down detection
- Traffic sign recognition: GTSRB-trained MobileNetV2 -> TensorFlow Lite for edge inference
- Sharp-turn detection via lane curvature estimation
- Vehicle speed management dashboard: percentage-based speed control
- Integrated Pygame dashboard for overlays and audio alerts

## Files of interest
- `integrated_driver_monitoring.py` – Main integrated application (threads, dashboard, drowsiness + lane)
- `Facerecognition/` – Drowsiness helper scripts and assets (alarm.wav)
- `Road Lane detection/Advanced-Lane-Lines/` – Lane detection pipeline and prepared test video
- `PROJECT_REPORT.md` – Detailed project report and methodology (created)

## Quick start (Raspberry Pi)
1. Clone project to Pi and enter project folder:

```bash
cd ~/Desktop
# copy or clone repo here
cd "M&I PROJECT - Updated"
```

2. Create and activate venv (Python 3.11 recommended):

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Run the integrated system:

```bash
python integrated_driver_monitoring.py
```

## Exit methods
- Press `Q` or `ESC` in the window
- Click the window Close (X) button
- Press `Ctrl+C` in the terminal (signal handler catches it)

## Notes and Raspberry Pi Tips
- All GUI operations are performed in the main thread to avoid Qt threading issues.
- If MediaPipe is used, ensure `numpy<2.0` in that environment; YOLO/PyTorch may require a separate venv due to different numpy requirements.
- For better performance on Raspberry Pi 5, consider increasing GPU memory and using TensorFlow Lite with quantized models.

## Methodology (short)
- Driver monitoring uses MediaPipe (or Dlib) landmarks and computes EAR/MAR for blink and yawn detection.
- Road perception runs a TFLite classifier trained on GTSRB; outputs are fused with lane curvature to detect sharp turns.
- All frames are processed in worker threads; the main thread composes combined frames and handles display + input.

## Mermaid flowchart
Use a Markdown renderer that supports Mermaid to visualize the flowchart included in `PROJECT_REPORT.md`.

## License & Contact
(Include your license or institution info here.)

---
Generated: November 16, 2025
