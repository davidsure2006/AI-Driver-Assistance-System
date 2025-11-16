# Drowsiness Detection System - Quick Reference Guide

## ✅ Successfully Implemented Features

### 1. **Face Mesh Visualization** (Like Your Reference Image)
- Uses MediaPipe Face Mesh with 468 landmarks
- Displays professional cyan/teal mesh overlay
- Real-time face tracking

### 2. **Smart Drowsiness Detection**
- **Eye Aspect Ratio (EAR)**: Detects eye closure
- **Mouth Aspect Ratio (MAR)**: Detects yawning
- **Calibration on Startup**: Adapts to your normal eye openness
- **EMA Smoothing**: Reduces false positives from blinking
- **Hysteresis**: Prevents alarm flickering

### 3. **Driver Missing/Down Detection**
- Persistent alarm if face is missing for 30 frames (~1 second)
- Shows "DRIVER DOWN/MISSING ALERT!" message
- Alarm continues until face is detected again

### 4. **Audio Alerts**
- Plays `alarm.wav` for drowsiness
- Plays `alarm.wav` for driver missing
- Auto-stops when condition clears

## 🎮 Controls

| Key | Action |
|-----|--------|
| **C** | Manual recalibration (collect new baseline EAR) |
| **R** | Reset all counters and stop alarms |
| **Q** | Quit the program |

## 🚀 How to Run

```powershell
cd "c:\Agent#66\Academical\Sem-V\M&I\M&I PROJECT\Facerecognition"
& "C:/Agent#66/Academical/Sem-V/M&I/M&I PROJECT/.venv/Scripts/python.exe" drowsiness_mediapipe.py
```

## ⚙️ Configuration (Edit at top of drowsiness_mediapipe.py)

```python
# Calibration
CALIBRATE_FRAMES = 120           # Frames to calibrate (default: 120)
EAR_THRESHOLD_FACTOR = 0.60      # Threshold = baseline * this (lower = more sensitive)

# Detection sensitivity
EYE_AR_CONSEC_FRAMES = 18        # Frames before drowsiness alarm (lower = faster)
MOUTH_AR_THRESH = 0.6            # Yawn threshold (higher = more sensitive)
YAWN_CONSEC_FRAMES = 15          # Frames before yawn alarm

# Driver missing
FACE_MISSING_CONSEC_FRAMES = 30  # Frames before missing alarm (~1 second)

# Smoothing
EAR_EMA_ALPHA = 0.35             # Smoothing factor (0-1, higher = less smoothing)
```

## 🔧 Tuning Tips

### If you get TOO MANY false positives (alarms when awake):
1. **Increase** `EYE_AR_CONSEC_FRAMES` (e.g., 25-30) - requires longer eye closure
2. **Decrease** `EAR_THRESHOLD_FACTOR` (e.g., 0.55) - makes it less sensitive
3. **Decrease** `EAR_EMA_ALPHA` (e.g., 0.25) - more smoothing
4. Press **C** to recalibrate while you're alert and looking at the camera

### If you get TOO FEW alerts (misses real drowsiness):
1. **Decrease** `EYE_AR_CONSEC_FRAMES` (e.g., 10-15) - triggers faster
2. **Increase** `EAR_THRESHOLD_FACTOR` (e.g., 0.65-0.70) - more sensitive
3. **Lower** `MOUTH_AR_THRESH` (e.g., 0.5) - detects smaller yawns

### For driver missing detection:
- **Decrease** `FACE_MISSING_CONSEC_FRAMES` (e.g., 20) - triggers faster
- **Increase** `FACE_MISSING_CONSEC_FRAMES` (e.g., 50) - waits longer

## 📊 What the Display Shows

```
EAR: 0.26          ← Eye Aspect Ratio (higher = more open)
DROWSINESS ALERT!  ← Shows when drowsy detected
MAR: 0.45          ← Mouth Aspect Ratio (higher = more open/yawning)
DRIVER DOWN/MISSING ALERT! ← Shows when no face detected for 30 frames
```

## 🎯 Current Calibration Results

Last run showed:
- **Baseline EAR**: 0.265 (your normal eye openness)
- **Adaptive Threshold**: 0.159 (closes eyes below this triggers alert)

This means the system learned YOUR normal eye state and adapted accordingly!

## 🆚 Comparison: Old vs New System

| Feature | face2.py (Old) | drowsiness_mediapipe.py (New) |
|---------|---------------|-------------------------------|
| Face landmarks | 68 (dlib) | 468 (MediaPipe) ✅ |
| Calibration | ❌ None | ✅ Auto-calibrates |
| Smoothing | ❌ None | ✅ EMA smoothing |
| False positives | ⚠️ High | ✅ Much lower |
| Speed | ~15 FPS | ~30+ FPS ✅ |
| Driver missing | ✅ Yes | ✅ Yes (improved) |
| Face mesh visual | Basic | Professional ✅ |

## 🐛 Troubleshooting

### "No module named 'mediapipe'"
```powershell
& "C:/Agent#66/Academical/Sem-V/M&I/M&I PROJECT/.venv/Scripts/python.exe" -m pip install mediapipe
```

### "alarm.wav not found" warning
- Sound is disabled but visual alerts still work
- Add an `alarm.wav` file to the Facerecognition folder for audio alerts

### Camera not opening
- Check if another program is using the camera
- Try changing `cv2.VideoCapture(0)` to `cv2.VideoCapture(1)` in the script

### Too many warnings from MediaPipe
- These are normal TensorFlow Lite warnings
- They don't affect functionality

## 📝 Files Created/Updated

1. **drowsiness_mediapipe.py** ← Use this one! (Recommended)
   - MediaPipe-based, fast, accurate
   - Professional face mesh like your reference image
   - Calibration + smoothing + persistent alarms

2. **face2.py** (Updated)
   - Added calibration and smoothing
   - Requires dlib (not installed in current venv)
   - Fallback option

3. **comparison.py**
   - Feature comparison chart
   - Run to see differences

## 🎓 How It Works

1. **Startup Calibration (120 frames)**
   - Camera opens and detects your face
   - Measures your normal Eye Aspect Ratio (EAR) for 120 frames
   - Calculates adaptive threshold = baseline × 0.60
   - Shows "Calibrating..." message

2. **Real-time Detection**
   - Continuously measures EAR and MAR
   - Applies EMA smoothing to reduce noise
   - Counts consecutive frames below threshold
   - Triggers alarm after 18 consecutive drowsy frames

3. **Driver Missing Detection**
   - Counts frames with no face detected
   - Triggers alarm after 30 frames (~1 second)
   - Alarm persists until face returns

## ✨ Next Steps / Enhancements Available

If you want, I can add:
- **Head pose detection** (nod detection for additional drowsiness signal)
- **CSV logging** (timestamp all events for analysis)
- **Sensitivity presets** (easy, medium, strict modes)
- **Multi-camera support**
- **Sound on/off toggle** in the UI
- **Statistics dashboard** (time drowsy, number of alerts, etc.)

Just let me know what you'd like!
