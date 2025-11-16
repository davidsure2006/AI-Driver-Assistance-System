# Raspberry Pi Setup Guide
## Driver Monitoring & Lane Detection System

---

## 📋 System Requirements

### Hardware Requirements
- **Raspberry Pi 4 Model B** (4GB or 8GB RAM recommended)
- **Raspberry Pi Camera Module** (v2 or v3) OR USB webcam
- **MicroSD Card**: 32GB or larger (Class 10 or better)
- **Power Supply**: Official 5V/3A USB-C power adapter
- **Cooling**: Heat sinks and/or fan (recommended for continuous operation)
- **Display**: HDMI monitor for setup and monitoring
- **Optional**: Speaker for audio alerts

### Software Requirements
- **OS**: Raspberry Pi OS (64-bit, Bullseye or Bookworm)
- **Python**: **3.9, 3.10, or 3.11 ONLY** (3.10 or 3.11 recommended)
  - ⚠️ **DO NOT use Python 3.13 or newer** - incompatible with MediaPipe and other dependencies
  - Check your version: `python3 --version`
- **Storage**: At least 5GB free space

---

## 🚀 Quick Setup (Automated)

For automatic installation, run the provided script:

```bash
chmod +x setup_raspberry_pi.sh
./setup_raspberry_pi.sh
```

The script will:
1. Update system packages
2. Install system dependencies
3. Create Python virtual environment
4. Install Python packages
5. Configure camera access
6. Set up performance optimizations

---

## 📝 Manual Setup Instructions

### Step 1: Update System

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y git
```

### Step 2: Install System Dependencies

```bash
# Core build tools
sudo apt install -y build-essential cmake pkg-config

# Image and video libraries
sudo apt install -y libjpeg-dev libtiff5-dev libpng-dev
sudo apt install -y libavcodec-dev libavformat-dev libswscale-dev libv4l-dev
sudo apt install -y libxvidcore-dev libx264-dev

# GUI libraries (for OpenCV)
sudo apt install -y libgtk-3-dev libcanberra-gtk3-dev

# Linear algebra and optimization
sudo apt install -y libatlas-base-dev gfortran

# Audio libraries (for pygame)
sudo apt install -y libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
sudo apt install -y libportmidi-dev libfreetype6-dev

# Python development
sudo apt install -y python3-dev python3-pip python3-venv

# FFmpeg for video processing
sudo apt install -y ffmpeg
```

### Step 3: Enable Camera

```bash
# Enable camera interface
sudo raspi-config
# Navigate to: Interface Options > Camera > Enable

# For Pi Camera Module, install picamera2
sudo apt install -y python3-picamera2

# Reboot to apply changes
sudo reboot
```

### Step 4: Configure GPU Memory

Edit boot configuration for better graphics performance:

```bash
sudo nano /boot/config.txt
```

Add or modify these lines:
```
# Increase GPU memory for better video processing
gpu_mem=256

# Enable camera
start_x=1
```

Save and reboot:
```bash
sudo reboot
```

### Step 5: Clone Project

```bash
cd ~
git clone <your-repository-url> driver-monitoring
cd driver-monitoring
```

Or copy your project files via USB/SCP.

### Step 6: Create Virtual Environment

```bash
# IMPORTANT: Verify Python version first
python3 --version
# Should show Python 3.9.x, 3.10.x, or 3.11.x
# If you see 3.13 or higher, install correct version:
# sudo apt install python3.11 python3.11-venv

# Create virtual environment with specific Python version
# Use python3.11, python3.10, or python3.9 (whichever is installed)
python3.11 -m venv venv
# OR: python3.10 -m venv venv
# OR: python3.9 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Verify Python version inside venv
python --version
# Should show 3.9.x, 3.10.x, or 3.11.x

# Upgrade pip
pip install --upgrade pip setuptools wheel
```

### Step 7: Install Python Dependencies

```bash
# Install all requirements
pip install -r requirements.txt

# This may take 20-40 minutes on Raspberry Pi
```

**Note**: If you encounter issues with MediaPipe or OpenCV:
```bash
# Install pre-built wheels for faster installation
pip install opencv-python-headless  # Lighter version without GUI
```

### Step 8: Test Camera

```bash
# Test USB camera
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('Camera OK' if cap.isOpened() else 'Camera Error')"

# Test Pi Camera Module
python3 -c "from picamera2 import Picamera2; cam = Picamera2(); print('Pi Camera OK')"
```

---

## ⚙️ Performance Optimization

### 1. Overclock Raspberry Pi (Optional)

Edit `/boot/config.txt`:
```bash
sudo nano /boot/config.txt
```

Add (for Pi 4):
```
# Overclock settings (safe values)
arm_freq=1800
over_voltage=2
gpu_freq=600
```

### 2. Enable Multithreading

The integrated system uses threading. Ensure all cores are utilized:
```bash
# Check CPU cores
nproc  # Should show 4 for Pi 4

# Monitor CPU usage during runtime
htop
```

### 3. Reduce Desktop Load

For production deployment, disable desktop:
```bash
sudo systemctl set-default multi-user.target
sudo reboot
```

To re-enable desktop:
```bash
sudo systemctl set-default graphical.target
```

### 4. Optimize Swap Memory

```bash
# Increase swap size for memory-intensive tasks
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# Change CONF_SWAPSIZE=100 to CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

---

## 🎯 Running the System

### Activate Virtual Environment
```bash
cd ~/driver-monitoring  # or your project directory
source venv/bin/activate
```

### Run Integrated System
```bash
python3 integrated_driver_monitoring.py
```

### Run Individual Modules

**Drowsiness Detection Only:**
```bash
cd Facerecognition
python3 drowsiness_detection_optimized.py
```

**Lane Detection Only:**
```bash
cd "Road Lane detection/Advanced-Lane-Lines"
python3 main.py
```

### Keyboard Controls
- **`q`**: Quit application
- **`ESC`**: Exit application

---

## 🔧 Troubleshooting

### Issue: Wrong Python Version

```bash
# Check current version
python3 --version

# If Python 3.13+ or other incompatible version:
# Install Python 3.11 (or 3.10)
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Verify installation
python3.11 --version

# Recreate virtual environment with correct version
rm -rf venv
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Issue: Camera Not Detected

```bash
# Check camera connection
vcgencmd get_camera

# Expected output: supported=1 detected=1

# List video devices
ls -l /dev/video*

# Test with raspistill (for Pi Camera)
raspistill -o test.jpg
```

### Issue: Low Frame Rate

1. **Reduce resolution** in the script:
   - Edit `integrated_driver_monitoring.py`
   - Change `cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)` to 320
   - Change `cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)` to 240

2. **Disable MediaPipe face mesh** (use lightweight detection)

3. **Lower GUI refresh rate**

### Issue: Memory Errors

```bash
# Monitor memory usage
free -h

# Close unnecessary services
sudo systemctl stop bluetooth
sudo systemctl stop cups
```

### Issue: Audio Alerts Not Working

```bash
# Test audio output
speaker-test -t wav -c 2

# Install additional audio libraries
sudo apt install -y pulseaudio pavucontrol

# Check pygame mixer
python3 -c "import pygame; pygame.mixer.init(); print('Audio OK')"
```

### Issue: ImportError for cv2 or mediapipe

```bash
# Check Python version first
python --version
# Must be 3.9.x, 3.10.x, or 3.11.x

# If Python 3.13+, recreate venv with correct version:
deactivate
rm -rf venv
python3.11 -m venv venv  # or python3.10
source venv/bin/activate

# Reinstall opencv
pip uninstall opencv-python opencv-contrib-python
pip install opencv-python==4.8.1.78

# For mediapipe issues, ensure compatible numpy
pip install numpy==1.23.5
pip install --force-reinstall mediapipe==0.10.9
```

---

## 📊 System Monitoring

### Check System Temperature
```bash
vcgencmd measure_temp
```

### Monitor Resource Usage
```bash
# Install htop if not present
sudo apt install htop

# Run monitoring
htop
```

### Auto-start on Boot (Optional)

Create systemd service:
```bash
sudo nano /etc/systemd/system/driver-monitor.service
```

Add:
```ini
[Unit]
Description=Driver Monitoring System
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/driver-monitoring
Environment="DISPLAY=:0"
ExecStart=/home/pi/driver-monitoring/venv/bin/python3 integrated_driver_monitoring.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Enable service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable driver-monitor.service
sudo systemctl start driver-monitor.service
```

---

## 📁 Project Structure

```
driver-monitoring/
├── integrated_driver_monitoring.py   # Main integrated system
├── Facerecognition/
│   ├── drowsiness_detection_optimized.py
│   └── requirements.txt
├── Road Lane detection/
│   └── Advanced-Lane-Lines/
│       ├── main.py
│       ├── LaneLines.py
│       ├── CameraCalibration.py
│       └── ...
├── requirements.txt                   # All Python dependencies
├── RASPBERRY_PI_SETUP.md             # This file
└── setup_raspberry_pi.sh             # Automated setup script
```

---

## 📚 Additional Resources

- [Raspberry Pi Documentation](https://www.raspberrypi.org/documentation/)
- [OpenCV on Raspberry Pi](https://docs.opencv.org/4.x/)
- [MediaPipe on Edge Devices](https://google.github.io/mediapipe/)
- [Python Virtual Environments](https://docs.python.org/3/library/venv.html)

---

## 🆘 Support

If you encounter issues:

1. Check system logs: `journalctl -xe`
2. Check Python errors in detail
3. Verify all dependencies: `pip list`
4. Test camera independently
5. Monitor temperature and throttling: `vcgencmd get_throttled`

---

**Last Updated**: November 2025  
**Tested On**: Raspberry Pi 4B (4GB/8GB), Raspberry Pi OS (64-bit Bookworm)
