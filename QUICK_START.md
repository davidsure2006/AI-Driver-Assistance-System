# 🚗 QUICK START GUIDE - Integrated Driver Monitoring System

## 🎯 What This System Does

✅ **Monitors driver drowsiness** using webcam + AI face detection  
✅ **Simulates lane detection** with real-time vehicle control  
✅ **Adjusts vehicle speed** based on driver alertness  
✅ **Sounds alarm** when driver is drowsy/down/missing  

---

## ▶️ How to Run

```bash
# From project directory:
cd "c:\Agent#66\Academical\Sem-V\M&I\M&I PROJECT"
python integrated_driver_monitoring.py
```

**What happens:**
1. System calibrates (looks at your eyes for 4 seconds)
2. Two windows open:
   - **Driver Monitoring** (your face with mesh)
   - **Lane Detection** (car driving simulation with lane lines)
3. Vehicle speed responds to your state

---

## ⏹️ How to Stop

### Simple: Press 'Q' in ANY window

1. **Click** on either window (to focus it)
2. **Press** 'Q' key
3. **Both windows close** automatically ✅

> **Tip:** Make sure the window border is highlighted before pressing Q

---

## 📊 Driver States

| State | Eyes | Head | Car Speed | Display Color |
|-------|------|------|-----------|---------------|
| **NORMAL** | Open | Up | 100% | 🟢 Green |
| **DROWSY** | Closed | Up | 50% | 🟠 Orange |
| **DRIVER DOWN** | Any | Down | STOPPED | 🔴 Red |
| **DRIVER MISSING** | None | None | STOPPED | 🔴 Red |

---

## 🎥 What You'll See

### Driver Monitoring Window:
```
┌─────────────────────────────────┐
│ EAR: 0.26                       │ ← Eye openness
│ NORMAL DRIVING                  │ ← Current state
│                                 │
│    [Your face with 468-point    │
│     mesh overlay in cyan]       │
│                                 │
│ MAR: 0.45                       │ ← Mouth openness
│ Pitch: 2.3deg                   │ ← Head angle
└─────────────────────────────────┘
```

### Lane Detection Window:
```
┌─────────────────────────────────┐
│ Driver State: NORMAL            │
│ Vehicle Status: NORMAL SPEED    │
│ Frame: 145/1260                 │
│                                 │
│  [Road view with GREEN lane     │
│   lines, curvature calculations,│
│   and position indicators]      │
│                                 │
└─────────────────────────────────┘
```

---

## 🔧 Troubleshooting

### "No camera detected"
- Check if webcam is connected
- Close other apps using camera (Zoom, Teams, etc.)
- Try: `python -c "import cv2; print(cv2.VideoCapture(0).isOpened())"`

### "Video not found"
- Verify file exists: `Road Lane detection\Advanced-Lane-Lines\output_videos\project_video_output.mp4`
- Re-run lane detection to generate output video

### "Q key not working"
- Click on the window first (border should be highlighted)
- Try uppercase 'Q' if CAPS LOCK is on
- Make sure window is not minimized

### "False drowsiness alerts"
- System is calibrating (wait 4 seconds)
- Ensure good lighting on your face
- Look directly at camera during calibration
- Adjust `EAR_THRESHOLD_FACTOR` in code (0.85 default)

### "Both windows not closing"
- This is now FIXED ✅
- Make sure you're running the latest version
- If still stuck, press Ctrl+C in terminal

---

## 📈 How Detection Works

### Eyes Closed Detection:
```
1. Calculate Eye Aspect Ratio (EAR)
2. Compare to calibrated baseline × 0.85
3. If low for 8 consecutive frames → DROWSY
4. Alarm sounds, car slows to 50%
```

### Head Down Detection:
```
1. Calculate head pitch angle from nose Z-position
2. If angle < -10° for 10 frames → DRIVER DOWN
3. Alarm sounds, car STOPS
```

### Driver Missing Detection:
```
1. No face detected by MediaPipe
2. If missing for 30 frames (1 second) → DRIVER MISSING
3. Alarm sounds, car STOPS
```

---

## 🎚️ Customization (Optional)

Edit `integrated_driver_monitoring.py`:

```python
# Make detection more/less sensitive:
CALIBRATE_FRAMES = 120        # Calibration time
EAR_THRESHOLD_FACTOR = 0.85   # Lower = more sensitive
EYE_AR_CONSEC_FRAMES = 8      # Frames before alert
HEAD_DOWN_PITCH_THRESH = -10  # Head down angle
FACE_MISSING_CONSEC_FRAMES = 30  # Missing time
```

---

## ✅ Quick Validation

After starting, verify:
- [ ] Calibration completes (4 seconds)
- [ ] Your face shows mesh overlay (cyan dots)
- [ ] Lane video shows green lane lines
- [ ] "NORMAL DRIVING" appears when alert
- [ ] Close eyes → "DROWSINESS ALERT" appears
- [ ] Tilt head down → "DRIVER DOWN ALERT" appears
- [ ] Move away → "DRIVER MISSING ALERT" appears
- [ ] Press Q → both windows close

---

## 🏆 System Requirements

**Hardware:**
- Webcam (720p or higher recommended)
- CPU: Any modern processor (GPU optional)
- RAM: 2GB+ available
- Storage: 100MB for dependencies

**Software:**
- Python 3.11.7
- Windows/Linux/Mac
- Dependencies: MediaPipe, OpenCV, NumPy, Pygame

**Already installed in:**
`C:/Agent#66/Academical/Sem-V/M&I/M&I PROJECT/.venv`

---

## 📞 Support

**Created:** November 9, 2025  
**Status:** ✅ Production Ready  
**Version:** 2.0 (with exit fix + processed video)

For detailed information, see:
- `SYSTEM_IMPROVEMENTS.md` - Recent changes
- `INTEGRATED_SYSTEM_GUIDE.md` - Full technical guide
- `HOW_TO_EXIT.md` - Exit troubleshooting

---

**Happy Monitoring! 🚗👁️**
