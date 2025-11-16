# Raspberry Pi Troubleshooting Guide

## If the Window Gets Stuck or Frozen

### Quick Exit Methods (in order of preference):

1. **Ctrl+C in Terminal**
   - Press `Ctrl+C` in the terminal where you ran the script
   - The signal handler will gracefully shut down the system
   - Should work even if the window is frozen

2. **Force Kill Python Process**
   ```bash
   pkill -9 python
   # or more specifically:
   pkill -9 -f integrated_driver_monitoring.py
   ```

3. **Force Close All OpenCV Windows**
   ```bash
   # Open a new terminal and run:
   pkill -9 python3.11
   ```

## Common Issues and Solutions

### Issue: Qt Threading Warnings
```
qt.qpa.plugin: Could not find the Qt platform plugin "wayland"
QObject::startTimer: Timers cannot be started from another thread
```

**Solution:** Already fixed in the latest version. All GUI operations now run in the main thread.

### Issue: Window Appears but is Frozen/Unresponsive

**Causes:**
- Qt backend threading restrictions on Raspberry Pi
- Wayland display server compatibility issues

**Solutions:**
1. **Switch to X11 (recommended for Raspberry Pi):**
   ```bash
   # Edit /boot/config.txt
   sudo nano /boot/config.txt
   # Add or ensure:
   dtoverlay=vc4-kms-v3d
   ```

2. **Force X11 display:**
   ```bash
   export QT_QPA_PLATFORM=xcb
   python integrated_driver_monitoring.py
   ```

3. **Use OpenCV without Qt:**
   ```bash
   # Reinstall OpenCV with different backend
   pip uninstall opencv-python
   pip install opencv-python-headless
   # Then reinstall regular version
   pip install opencv-python
   ```

### Issue: Camera Not Found

```
Could not open camera for drowsiness detection
```

**Solutions:**
1. **Enable camera in raspi-config:**
   ```bash
   sudo raspi-config
   # Navigate to: Interface Options -> Camera -> Enable
   # Reboot after enabling
   sudo reboot
   ```

2. **Check camera connection:**
   ```bash
   vcgencmd get_camera
   # Should show: supported=1 detected=1
   
   # Test camera:
   libcamera-still -o test.jpg
   ```

3. **Check camera permissions:**
   ```bash
   # Add user to video group
   sudo usermod -a -G video $USER
   # Logout and login again
   ```

4. **Try different camera index:**
   Edit `integrated_driver_monitoring.py` line ~126:
   ```python
   cap = cv2.VideoCapture(0)  # Try 1, 2, etc. if 0 doesn't work
   ```

### Issue: Video File Not Found

```
[ERROR] Video not found: Road Lane detection/Advanced-Lane-Lines/output_videos/project_video_output.mp4
```

**Solution:**
```bash
# Verify file exists:
ls -la "Road Lane detection/Advanced-Lane-Lines/output_videos/"

# If missing, you need to generate it:
cd "Road Lane detection/Advanced-Lane-Lines"
python main.py
```

### Issue: Slow Performance / Low FPS

**Solutions:**
1. **Increase GPU memory (Raspberry Pi 4/5):**
   ```bash
   sudo nano /boot/config.txt
   # Add or modify:
   gpu_mem=256
   # Reboot
   sudo reboot
   ```

2. **Disable desktop effects:**
   ```bash
   # Run from terminal instead of desktop
   # Or use lite version of Raspberry Pi OS
   ```

3. **Reduce MediaPipe model complexity:**
   Edit `integrated_driver_monitoring.py` line ~99:
   ```python
   face_mesh = mp_face_mesh.FaceMesh(
       static_image_mode=False,
       max_num_faces=1,
       refine_landmarks=False,  # Change to False for better performance
       min_detection_confidence=0.3,  # Lower for faster detection
       min_tracking_confidence=0.3
   )
   ```

### Issue: Alarm Sound Not Playing

```
[WARN] alarm.wav not found - sound disabled
```

**Solutions:**
1. **Check if file exists:**
   ```bash
   ls -la Facerecognition/alarm.wav
   ```

2. **Install pygame audio dependencies:**
   ```bash
   sudo apt-get install libsdl2-mixer-2.0-0
   ```

3. **Test audio output:**
   ```bash
   # Play a test sound
   aplay /usr/share/sounds/alsa/Front_Center.wav
   ```

## Performance Optimization for Raspberry Pi

### Recommended Settings

1. **Overclock (Raspberry Pi 4):**
   ```bash
   sudo nano /boot/config.txt
   # Add:
   over_voltage=6
   arm_freq=2000
   gpu_freq=750
   ```

2. **Disable unnecessary services:**
   ```bash
   sudo systemctl disable bluetooth
   sudo systemctl disable cups
   ```

3. **Run from console (no desktop):**
   ```bash
   # Ctrl+Alt+F1 to switch to console
   # Login and run:
   DISPLAY=:0 python integrated_driver_monitoring.py
   ```

## Exit Methods Reference

The system now supports multiple exit methods:

1. **Q key** - Press Q (or q) in the window
2. **ESC key** - Press Escape in the window  
3. **X button** - Click the window close button
4. **Ctrl+C** - Press Ctrl+C in the terminal
5. **Window close detection** - System auto-exits if window is closed

All methods should work even if the window appears frozen.

## Verify System is Working

After starting, you should see:
```
[INFO] Drowsiness Detection Started
[INFO] Lane Detection Started
[INFO] Video: 1260 frames at 25 FPS
[INFO] Starting main display loop...
[INFO] Press Q or ESC to exit, or Ctrl+C in terminal
[INFO] Calibration complete baseline_ear=0.XXX
```

During calibration (first ~2 seconds):
- Look straight ahead
- Keep eyes open
- Window shows "CALIBRATING... (X/60)"

After calibration:
- Window shows integrated view
- Driver monitor in top-left corner
- Dashboard below driver monitor
- Lane detection video playing in background

## Still Having Issues?

1. **Check Python version:**
   ```bash
   python --version  # Should be 3.11.7
   ```

2. **Verify all packages installed:**
   ```bash
   pip list | grep -E "opencv|mediapipe|numpy|pygame|scipy"
   ```

3. **Check system resources:**
   ```bash
   # Monitor CPU and memory usage
   htop
   ```

4. **View full error log:**
   ```bash
   python integrated_driver_monitoring.py 2>&1 | tee error.log
   ```

5. **Run with verbose OpenCV debugging:**
   ```bash
   export OPENCV_LOG_LEVEL=DEBUG
   python integrated_driver_monitoring.py
   ```
