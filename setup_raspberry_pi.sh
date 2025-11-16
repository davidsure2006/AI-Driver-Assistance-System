#!/bin/bash

################################################################################
# Raspberry Pi Setup Script
# Driver Monitoring & Lane Detection System
#
# This script automates the installation and configuration of the driver
# monitoring system on Raspberry Pi
#
# Usage: chmod +x setup_raspberry_pi.sh && ./setup_raspberry_pi.sh
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "\n${GREEN}=====================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}=====================================${NC}\n"
}

################################################################################
# Check if running on Raspberry Pi
################################################################################

print_header "Checking System Compatibility"

if [ ! -f /proc/device-tree/model ]; then
    print_error "This script is designed for Raspberry Pi"
    exit 1
fi

MODEL=$(cat /proc/device-tree/model)
print_status "Detected: $MODEL"

if [[ ! "$MODEL" == *"Raspberry Pi"* ]]; then
    print_warning "This may not be a Raspberry Pi. Continue anyway? (y/n)"
    read -r response
    if [[ ! "$response" =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

################################################################################
# Check Python Version
################################################################################

print_header "Checking Python Version"

# Get Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

print_status "Default Python version: $PYTHON_VERSION"

# Check if version is compatible (3.9, 3.10, or 3.11)
PYTHON_OK=false
if [ "$PYTHON_MAJOR" -eq 3 ]; then
    if [ "$PYTHON_MINOR" -ge 9 ] && [ "$PYTHON_MINOR" -le 11 ]; then
        PYTHON_OK=true
        PYTHON_CMD="python3"
        print_success "Python $PYTHON_VERSION is compatible"
    fi
fi

# If default python3 is not compatible, try to find compatible version
if [ "$PYTHON_OK" = false ]; then
    print_warning "Python $PYTHON_VERSION is not compatible (need 3.9-3.11)"
    print_status "Searching for compatible Python versions..."
    
    # Try to find python3.11, 3.10, or 3.9
    for version in 3.11 3.10 3.9; do
        if command -v python${version} &> /dev/null; then
            PYTHON_CMD="python${version}"
            PYTHON_VERSION=$(${PYTHON_CMD} --version 2>&1 | awk '{print $2}')
            print_success "Found compatible Python: $PYTHON_VERSION"
            PYTHON_OK=true
            break
        fi
    done
fi

# If still no compatible version, offer to install
if [ "$PYTHON_OK" = false ]; then
    print_error "No compatible Python version found (need 3.9, 3.10, or 3.11)"
    print_status "Would you like to install Python 3.11? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        print_status "Installing Python 3.11..."
        sudo apt update
        sudo apt install -y python3.11 python3.11-venv python3.11-dev
        PYTHON_CMD="python3.11"
        PYTHON_VERSION=$(${PYTHON_CMD} --version 2>&1 | awk '{print $2}')
        print_success "Python $PYTHON_VERSION installed"
        PYTHON_OK=true
    else
        print_error "Cannot proceed without compatible Python version"
        exit 1
    fi
fi

print_success "Using Python command: $PYTHON_CMD"

################################################################################
# Update System
################################################################################

print_header "Updating System Packages"

print_status "Running apt update..."
sudo apt update

print_status "Upgrading packages (this may take several minutes)..."
sudo apt upgrade -y

print_success "System updated successfully"

################################################################################
# Install System Dependencies
################################################################################

print_header "Installing System Dependencies"

print_status "Installing build tools..."
sudo apt install -y \
    build-essential \
    cmake \
    pkg-config \
    git \
    wget \
    curl

print_status "Installing image and video libraries..."
sudo apt install -y \
    libjpeg-dev \
    libtiff5-dev \
    libpng-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev

print_status "Installing GUI libraries..."
sudo apt install -y \
    libgtk-3-dev \
    libcanberra-gtk3-dev

print_status "Installing numerical libraries..."
sudo apt install -y \
    libatlas-base-dev \
    gfortran

print_status "Installing audio libraries (for pygame)..."
sudo apt install -y \
    libsdl2-dev \
    libsdl2-image-dev \
    libsdl2-mixer-dev \
    libsdl2-ttf-dev \
    libportmidi-dev \
    libfreetype6-dev

print_status "Installing Python development tools..."
sudo apt install -y \
    python3-dev \
    python3-pip \
    python3-venv

print_status "Installing FFmpeg..."
sudo apt install -y ffmpeg

print_status "Installing camera support (for Pi Camera Module)..."
sudo apt install -y python3-picamera2 || print_warning "picamera2 not available (may need manual install)"

print_success "All system dependencies installed"

################################################################################
# Configure Camera
################################################################################

print_header "Camera Configuration"

print_status "Checking camera status..."
CAMERA_STATUS=$(vcgencmd get_camera 2>/dev/null || echo "unknown")
print_status "Camera status: $CAMERA_STATUS"

if [[ "$CAMERA_STATUS" != *"detected=1"* ]]; then
    print_warning "Camera not detected. Make sure:"
    print_warning "  1. Camera is properly connected"
    print_warning "  2. Camera interface is enabled in raspi-config"
    print_warning "  3. You've rebooted after enabling camera"
    echo ""
    print_status "Would you like to enable camera interface now? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        print_status "Please enable camera in the Interface Options menu"
        sleep 2
        sudo raspi-config
    fi
fi

################################################################################
# Configure GPU Memory
################################################################################

print_header "GPU Memory Configuration"

if [ -f /boot/config.txt ]; then
    BOOT_CONFIG="/boot/config.txt"
elif [ -f /boot/firmware/config.txt ]; then
    BOOT_CONFIG="/boot/firmware/config.txt"
else
    print_error "Could not find boot config file"
    BOOT_CONFIG=""
fi

if [ -n "$BOOT_CONFIG" ]; then
    print_status "Configuring GPU memory in $BOOT_CONFIG..."
    
    # Backup config
    sudo cp "$BOOT_CONFIG" "${BOOT_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
    
    # Check if gpu_mem is already set
    if grep -q "^gpu_mem=" "$BOOT_CONFIG"; then
        print_status "GPU memory already configured"
    else
        print_status "Setting GPU memory to 256MB..."
        echo "" | sudo tee -a "$BOOT_CONFIG" > /dev/null
        echo "# GPU memory for driver monitoring system" | sudo tee -a "$BOOT_CONFIG" > /dev/null
        echo "gpu_mem=256" | sudo tee -a "$BOOT_CONFIG" > /dev/null
        print_success "GPU memory configured (will take effect after reboot)"
    fi
fi

################################################################################
# Create Virtual Environment
################################################################################

print_header "Setting Up Python Virtual Environment"

VENV_DIR="venv"

if [ -d "$VENV_DIR" ]; then
    print_warning "Virtual environment already exists at $VENV_DIR"
    print_status "Remove and recreate? (y/n)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
    else
        print_status "Using existing virtual environment"
    fi
fi

if [ ! -d "$VENV_DIR" ]; then
    print_status "Creating virtual environment with $PYTHON_CMD..."
    $PYTHON_CMD -m venv "$VENV_DIR"
    print_success "Virtual environment created"
fi

print_status "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Verify Python version in venv
VENV_PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
print_status "Virtual environment Python version: $VENV_PYTHON_VERSION"

# Double-check venv Python version
VENV_MAJOR=$(echo $VENV_PYTHON_VERSION | cut -d. -f1)
VENV_MINOR=$(echo $VENV_PYTHON_VERSION | cut -d. -f2)

if [ "$VENV_MAJOR" -ne 3 ] || [ "$VENV_MINOR" -lt 9 ] || [ "$VENV_MINOR" -gt 11 ]; then
    print_error "Virtual environment has wrong Python version: $VENV_PYTHON_VERSION"
    print_error "Expected: 3.9.x, 3.10.x, or 3.11.x"
    exit 1
fi

print_status "Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

################################################################################
# Install Python Dependencies
################################################################################

print_header "Installing Python Dependencies"

if [ ! -f "requirements.txt" ]; then
    print_error "requirements.txt not found in current directory"
    print_status "Please ensure you're running this script from the project root"
    exit 1
fi

print_status "Installing Python packages from requirements.txt..."
print_warning "This may take 20-40 minutes on Raspberry Pi. Please be patient..."

# Install packages with progress
pip install -r requirements.txt --verbose

print_success "Python dependencies installed"

################################################################################
# Test Installation
################################################################################

print_header "Testing Installation"

print_status "Testing OpenCV..."
python3 -c "import cv2; print(f'OpenCV version: {cv2.__version__}')" && \
    print_success "OpenCV OK" || print_error "OpenCV import failed"

print_status "Testing NumPy..."
python3 -c "import numpy as np; print(f'NumPy version: {np.__version__}')" && \
    print_success "NumPy OK" || print_error "NumPy import failed"

print_status "Testing MediaPipe..."
python3 -c "import mediapipe as mp; print(f'MediaPipe version: {mp.__version__}')" && \
    print_success "MediaPipe OK" || print_error "MediaPipe import failed"

print_status "Testing pygame..."
python3 -c "import pygame; pygame.mixer.init(); print(f'pygame version: {pygame.__version__}')" && \
    print_success "pygame OK" || print_error "pygame import failed"

print_status "Testing scipy..."
python3 -c "import scipy; print(f'scipy version: {scipy.__version__}')" && \
    print_success "scipy OK" || print_error "scipy import failed"

print_status "Testing camera access..."
python3 -c "import cv2; cap = cv2.VideoCapture(0); print('Camera:', 'OK' if cap.isOpened() else 'ERROR'); cap.release()" || \
    print_warning "Camera test failed (may need USB camera connected)"

################################################################################
# System Information
################################################################################

print_header "System Information"

print_status "Python version:"
python3 --version

print_status "CPU temperature:"
vcgencmd measure_temp

print_status "Memory status:"
free -h

print_status "Disk space:"
df -h | grep -E '^/dev/root|^Filesystem'

################################################################################
# Final Instructions
################################################################################

print_header "Setup Complete!"

print_success "Installation successful!"
echo ""
print_status "Next steps:"
echo "  1. Activate virtual environment:"
echo "     ${GREEN}source venv/bin/activate${NC}"
echo ""
print_status "  2. Run the integrated system:"
echo "     ${GREEN}python3 integrated_driver_monitoring.py${NC}"
echo ""
print_status "  3. Or run individual modules:"
echo "     ${GREEN}python3 Facerecognition/drowsiness_detection_optimized.py${NC}"
echo "     ${GREEN}cd 'Road Lane detection/Advanced-Lane-Lines' && python3 main.py${NC}"
echo ""

if [[ "$CAMERA_STATUS" != *"detected=1"* ]]; then
    print_warning "Camera was not detected. Please:"
    print_warning "  1. Connect your camera (USB or Pi Camera Module)"
    print_warning "  2. Enable camera interface: sudo raspi-config"
    print_warning "  3. Reboot: sudo reboot"
    echo ""
fi

if grep -q "gpu_mem=256" "$BOOT_CONFIG" 2>/dev/null; then
    print_warning "GPU memory has been configured. Reboot recommended:"
    print_status "  ${GREEN}sudo reboot${NC}"
    echo ""
fi

print_status "For detailed information, see: ${BLUE}RASPBERRY_PI_SETUP.md${NC}"
print_status "For troubleshooting, check system logs: ${BLUE}journalctl -xe${NC}"

echo ""
print_success "Happy monitoring! 🚗👁️"
echo ""

################################################################################
# End of script
################################################################################
