"""
Advanced Drowsiness Detection System with MediaPipe Face Mesh
Features:
- High-performance face mesh with 468 landmarks (like the reference image)
- Improved EAR (Eye Aspect Ratio) calculation
- MAR (Mouth Aspect Ratio) for yawning detection
- Head pose estimation (pitch, yaw, roll)
- Face missing/driver down detection
- Visual feedback with professional UI
- Optimized performance
"""

import cv2
import numpy as np
import mediapipe as mp
from scipy.spatial import distance as dist
import pygame
import os
import time

# ==================== CONFIGURATION ====================

# Eye Aspect Ratio (EAR) thresholds
EYE_AR_THRESH = 0.22  # Optimized threshold for drowsiness detection
EYE_AR_CONSEC_FRAMES = 15  # Frames before triggering alarm

# Mouth Aspect Ratio (MAR) thresholds
MOUTH_AR_THRESH = 0.6  # Threshold for yawn detection
YAWN_CONSEC_FRAMES = 15

# Head pose thresholds (degrees)
HEAD_PITCH_THRESH = 20  # Forward/backward tilt
HEAD_YAW_THRESH = 25    # Left/right turn

# Face missing detection
FACE_MISSING_CONSEC_FRAMES = 30  # Frames before "driver missing" alarm

# Alarm settings
ALARM_SOUND_FILE = "alarm.wav"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALARM_SOUND_PATH = os.path.join(SCRIPT_DIR, ALARM_SOUND_FILE)

# Visual settings
MESH_COLOR = (0, 255, 255)  # Cyan mesh like the reference image
MESH_THICKNESS = 1
POINT_COLOR = (0, 200, 200)
WARNING_COLOR = (0, 0, 255)  # Red
INFO_COLOR = (255, 255, 255)  # White
GOOD_COLOR = (0, 255, 0)  # Green

# ==================== MEDIAPIPE SETUP ====================

mp_face_mesh = mp.solutions.face_mesh
mp_drawing = mp.solutions.drawing_utils
mp_drawing_styles = mp.solutions.drawing_styles

# Face mesh landmark indices for eyes and mouth
# MediaPipe Face Mesh landmark indices
LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
MOUTH_INDICES = [61, 291, 39, 181, 0, 17, 269, 405]

# Head pose estimation landmarks
FACE_3D_POINTS = np.array([
    [0.0, 0.0, 0.0],           # Nose tip
    [0.0, -330.0, -65.0],      # Chin
    [-225.0, 170.0, -135.0],   # Left eye left corner
    [225.0, 170.0, -135.0],    # Right eye right corner
    [-150.0, -150.0, -125.0],  # Left mouth corner
    [150.0, -150.0, -125.0]    # Right mouth corner
], dtype=np.float64)

FACE_2D_LANDMARKS = [1, 152, 33, 263, 61, 291]  # Corresponding 2D indices

# ==================== HELPER FUNCTIONS ====================

def calculate_ear(landmarks, eye_indices, img_w, img_h):
    """Calculate Eye Aspect Ratio using MediaPipe landmarks"""
    # Get eye coordinates
    eye_points = []
    for idx in eye_indices:
        x = int(landmarks[idx].x * img_w)
        y = int(landmarks[idx].y * img_h)
        eye_points.append([x, y])
    
    eye_points = np.array(eye_points)
    
    # EAR formula
    # Vertical distances
    A = dist.euclidean(eye_points[1], eye_points[5])
    B = dist.euclidean(eye_points[2], eye_points[4])
    # Horizontal distance
    C = dist.euclidean(eye_points[0], eye_points[3])
    
    ear = (A + B) / (2.0 * C)
    return ear, eye_points

def calculate_mar(landmarks, mouth_indices, img_w, img_h):
    """Calculate Mouth Aspect Ratio using MediaPipe landmarks"""
    # Get mouth coordinates
    mouth_points = []
    for idx in mouth_indices:
        x = int(landmarks[idx].x * img_w)
        y = int(landmarks[idx].y * img_h)
        mouth_points.append([x, y])
    
    mouth_points = np.array(mouth_points)
    
    # MAR formula
    # Vertical distances
    A = dist.euclidean(mouth_points[1], mouth_points[7])
    B = dist.euclidean(mouth_points[2], mouth_points[6])
    C = dist.euclidean(mouth_points[3], mouth_points[5])
    # Horizontal distance
    D = dist.euclidean(mouth_points[0], mouth_points[4])
    
    mar = (A + B + C) / (3.0 * D)
    return mar, mouth_points

def estimate_head_pose(landmarks, img_w, img_h, camera_matrix, dist_coeffs):
    """Estimate head pose (pitch, yaw, roll) using PnP algorithm"""
    # Get 2D landmarks
    face_2d = []
    for idx in FACE_2D_LANDMARKS:
        x = int(landmarks[idx].x * img_w)
        y = int(landmarks[idx].y * img_h)
        face_2d.append([x, y])
    
    face_2d = np.array(face_2d, dtype=np.float64)
    
    # Solve PnP
    success, rot_vec, trans_vec = cv2.solvePnP(
        FACE_3D_POINTS, face_2d, camera_matrix, dist_coeffs, 
        flags=cv2.SOLVEPNP_ITERATIVE
    )
    
    # Convert rotation vector to rotation matrix
    rmat, _ = cv2.Rodrigues(rot_vec)
    
    # Calculate Euler angles
    angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
    
    # Get pitch, yaw, roll
    pitch = angles[0] * 360
    yaw = angles[1] * 360
    roll = angles[2] * 360
    
    return pitch, yaw, roll

def draw_professional_ui(frame, ear, mar, pitch, yaw, status, ear_counter, mar_counter, face_missing_counter, fps):
    """Draw professional UI overlay with metrics"""
    h, w = frame.shape[:2]
    
    # Create semi-transparent overlay panel
    overlay = frame.copy()
    panel_h = 200
    cv2.rectangle(overlay, (0, 0), (w, panel_h), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.4, frame, 0.6, 0, frame)
    
    # Status banner
    if "DROWSINESS" in status:
        color = WARNING_COLOR
        status_bg = (0, 0, 100)
    elif "MISSING" in status:
        color = WARNING_COLOR
        status_bg = (0, 0, 100)
    else:
        color = GOOD_COLOR
        status_bg = (0, 50, 0)
    
    cv2.rectangle(frame, (0, 0), (w, 50), status_bg, -1)
    cv2.putText(frame, status, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
    
    # Metrics display
    y_offset = 70
    metrics = [
        f"EAR: {ear:.3f} (Thresh: {EYE_AR_THRESH})",
        f"MAR: {mar:.3f} (Thresh: {MOUTH_AR_THRESH})",
        f"Head Pitch: {pitch:.1f}° | Yaw: {yaw:.1f}°",
        f"Eye Closure: {ear_counter} frames | Yawn: {mar_counter} frames",
        f"FPS: {fps:.1f}"
    ]
    
    for i, metric in enumerate(metrics):
        y_pos = y_offset + (i * 25)
        # Highlight warnings
        if i == 0 and ear < EYE_AR_THRESH:
            cv2.putText(frame, metric, (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WARNING_COLOR, 2)
        elif i == 1 and mar > MOUTH_AR_THRESH:
            cv2.putText(frame, metric, (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WARNING_COLOR, 2)
        else:
            cv2.putText(frame, metric, (20, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, INFO_COLOR, 1)
    
    # Instructions
    cv2.putText(frame, "Press 'Q' to quit | 'R' to reset", (w - 350, h - 20), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, INFO_COLOR, 1)
    
    return frame

# ==================== MAIN APPLICATION ====================

class DrowsinessDetector:
    def __init__(self):
        """Initialize the drowsiness detection system"""
        print("="*60)
        print("Advanced Drowsiness Detection System")
        print("="*60)
        
        # Initialize pygame mixer for alarm
        pygame.mixer.init()
        
        # Load alarm sound
        try:
            print("[INFO] Loading alarm sound...")
            self.alarm_sound = pygame.mixer.Sound(ALARM_SOUND_PATH)
            print("[SUCCESS] Alarm sound loaded")
        except pygame.error as e:
            print(f"[WARNING] Alarm sound file not found: {e}")
            print("[INFO] System will work without audio alerts")
            self.alarm_sound = None
        
        # Initialize MediaPipe Face Mesh
        print("[INFO] Initializing MediaPipe Face Mesh...")
        self.face_mesh = mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        print("[SUCCESS] Face Mesh initialized")
        
        # State variables
        self.ear_counter = 0
        self.mar_counter = 0
        self.face_missing_counter = 0
        self.drowsiness_alarm_on = False
        self.missing_alarm_on = False
        
        # Camera setup
        print("[INFO] Initializing camera...")
        self.cap = cv2.VideoCapture(0)
        
        if not self.cap.isOpened():
            print("[ERROR] Cannot access camera")
            raise RuntimeError("Camera not accessible")
        
        # Get camera properties
        self.img_w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.img_h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[INFO] Camera resolution: {self.img_w}x{self.img_h}")
        
        # Camera matrix for head pose estimation
        focal_length = self.img_w
        center = (self.img_w / 2, self.img_h / 2)
        self.camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float64)
        
        self.dist_coeffs = np.zeros((4, 1))
        
        # FPS tracking
        self.prev_time = time.time()
        self.fps = 0
        
        print("[SUCCESS] System ready!")
        print("\nStarting detection...")
        print("="*60)
    
    def reset_counters(self):
        """Reset all detection counters"""
        self.ear_counter = 0
        self.mar_counter = 0
        self.face_missing_counter = 0
        if self.drowsiness_alarm_on and self.alarm_sound:
            self.alarm_sound.stop()
            self.drowsiness_alarm_on = False
        if self.missing_alarm_on and self.alarm_sound:
            self.alarm_sound.stop()
            self.missing_alarm_on = False
        print("[INFO] Counters reset")
    
    def process_frame(self, frame):
        """Process a single frame for drowsiness detection"""
        # Flip for mirror effect
        frame = cv2.flip(frame, 1)
        
        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Process with MediaPipe
        results = self.face_mesh.process(rgb_frame)
        
        # Default values
        ear = 0.0
        mar = 0.0
        pitch = 0.0
        yaw = 0.0
        status = "Monitoring..."
        
        # Calculate FPS
        current_time = time.time()
        self.fps = 1 / (current_time - self.prev_time)
        self.prev_time = current_time
        
        # Check if face is detected
        if results.multi_face_landmarks:
            # Face detected - reset missing counter
            self.face_missing_counter = 0
            if self.missing_alarm_on and self.alarm_sound:
                self.alarm_sound.stop()
                self.missing_alarm_on = False
            
            # Get first face landmarks
            face_landmarks = results.multi_face_landmarks[0]
            
            # Draw face mesh (like the reference image)
            mp_drawing.draw_landmarks(
                image=frame,
                landmark_list=face_landmarks,
                connections=mp_face_mesh.FACEMESH_TESSELATION,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles.DrawingSpec(
                    color=MESH_COLOR, 
                    thickness=MESH_THICKNESS
                )
            )
            
            # Draw contours for better visibility
            mp_drawing.draw_landmarks(
                image=frame,
                landmark_list=face_landmarks,
                connections=mp_face_mesh.FACEMESH_CONTOURS,
                landmark_drawing_spec=None,
                connection_drawing_spec=mp_drawing_styles.DrawingSpec(
                    color=(0, 255, 0), 
                    thickness=1
                )
            )
            
            landmarks = face_landmarks.landmark
            
            # Calculate EAR for both eyes
            left_ear, left_eye_points = calculate_ear(landmarks, LEFT_EYE_INDICES, self.img_w, self.img_h)
            right_ear, right_eye_points = calculate_ear(landmarks, RIGHT_EYE_INDICES, self.img_w, self.img_h)
            ear = (left_ear + right_ear) / 2.0
            
            # Calculate MAR
            mar, mouth_points = calculate_mar(landmarks, MOUTH_INDICES, self.img_w, self.img_h)
            
            # Estimate head pose
            pitch, yaw, roll = estimate_head_pose(landmarks, self.img_w, self.img_h, 
                                                  self.camera_matrix, self.dist_coeffs)
            
            # Draw eye and mouth regions
            for point in left_eye_points:
                cv2.circle(frame, tuple(point), 2, (0, 255, 0), -1)
            for point in right_eye_points:
                cv2.circle(frame, tuple(point), 2, (0, 255, 0), -1)
            
            # Update counters
            if ear < EYE_AR_THRESH:
                self.ear_counter += 1
            else:
                self.ear_counter = 0
            
            if mar > MOUTH_AR_THRESH:
                self.mar_counter += 1
            else:
                self.mar_counter = 0
            
            # Check for drowsiness
            drowsy = False
            
            # Eyes closed for too long
            if self.ear_counter >= EYE_AR_CONSEC_FRAMES:
                drowsy = True
                status = "⚠ DROWSINESS ALERT - EYES CLOSED!"
            
            # Yawning for too long
            elif self.mar_counter >= YAWN_CONSEC_FRAMES:
                drowsy = True
                status = "⚠ DROWSINESS ALERT - YAWNING!"
            
            # Combined: eyes closing while yawning
            elif ear < EYE_AR_THRESH and mar > MOUTH_AR_THRESH:
                drowsy = True
                status = "⚠ DROWSINESS ALERT - COMBINED!"
            
            # Head pose abnormal (looking away or head down)
            elif abs(pitch) > HEAD_PITCH_THRESH or abs(yaw) > HEAD_YAW_THRESH:
                drowsy = True
                status = "⚠ ATTENTION ALERT - HEAD POSE!"
            
            # Trigger or stop alarm
            if drowsy:
                if not self.drowsiness_alarm_on and self.alarm_sound:
                    self.drowsiness_alarm_on = True
                    print(f"[ALERT] {status}")
                    self.alarm_sound.play(-1)
            else:
                if self.drowsiness_alarm_on and self.alarm_sound:
                    self.drowsiness_alarm_on = False
                    self.alarm_sound.stop()
                status = "✓ DRIVER ALERT"
        
        else:
            # No face detected
            self.ear_counter = 0
            self.mar_counter = 0
            self.face_missing_counter += 1
            
            # Stop drowsiness alarm if active
            if self.drowsiness_alarm_on and self.alarm_sound:
                self.drowsiness_alarm_on = False
                self.alarm_sound.stop()
            
            # Check for missing driver
            if self.face_missing_counter >= FACE_MISSING_CONSEC_FRAMES:
                status = "⚠ DRIVER MISSING/DOWN ALERT!"
                if not self.missing_alarm_on and self.alarm_sound:
                    self.missing_alarm_on = True
                    print("[ALERT] Driver missing or down!")
                    self.alarm_sound.play(-1)
            else:
                status = f"Searching for face... ({self.face_missing_counter}/{FACE_MISSING_CONSEC_FRAMES})"
        
        # Draw professional UI
        frame = draw_professional_ui(frame, ear, mar, pitch, yaw, status, 
                                     self.ear_counter, self.mar_counter, 
                                     self.face_missing_counter, self.fps)
        
        return frame
    
    def run(self):
        """Main detection loop"""
        try:
            while True:
                ret, frame = self.cap.read()
                
                if not ret:
                    print("[ERROR] Failed to read frame")
                    break
                
                # Process frame
                processed_frame = self.process_frame(frame)
                
                # Display
                cv2.imshow("Advanced Drowsiness Detection System", processed_frame)
                
                # Handle key presses
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q') or key == ord('Q'):
                    print("\n[INFO] Quitting...")
                    break
                elif key == ord('r') or key == ord('R'):
                    self.reset_counters()
        
        finally:
            # Cleanup
            print("[INFO] Cleaning up...")
            if self.alarm_sound:
                self.alarm_sound.stop()
            self.cap.release()
            cv2.destroyAllWindows()
            pygame.mixer.quit()
            print("[INFO] System shutdown complete")

# ==================== ENTRY POINT ====================

def main():
    try:
        detector = DrowsinessDetector()
        detector.run()
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
