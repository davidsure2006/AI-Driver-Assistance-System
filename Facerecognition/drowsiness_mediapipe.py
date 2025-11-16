"""
MediaPipe-based Drowsiness Detection
- Uses MediaPipe Face Mesh (468 landmarks) for robust, fast landmark detection
- Computes Eye Aspect Ratio (EAR) and Mouth Aspect Ratio (MAR) using face-mesh indices
- Calibration phase on startup to compute baseline EAR
- EMA smoothing, hysteresis and persistent missing-driver alarm
- Controls: 'c' = recalibrate, 'r' = reset counters, 'q' = quit

Requires: mediapipe, opencv-python, numpy, pygame
"""

import cv2
import mediapipe as mp
import numpy as np
import pygame
import os
import time

# Config
CALIBRATE_FRAMES = 0  # No calibration - use fallback threshold immediately
EAR_THRESHOLD_FACTOR = 0.85        # Increased - more sensitive to eye closure
EAR_EMA_ALPHA = 0.35
EYE_AR_CONSEC_FRAMES = 8           # Reduced - faster detection (was 12)
MOUTH_AR_THRESH = 0.75             # Increased to avoid false yawn detection from talking
YAWN_CONSEC_FRAMES = 20            # Increased to avoid detecting talking as yawning
FACE_MISSING_CONSEC_FRAMES = 30
HEAD_DOWN_PITCH_THRESH = -10.0     # Less strict - easier to trigger (was -15.0)
HEAD_DOWN_CONSEC_FRAMES = 10       # Reduced - faster detection (was 15)
ALARM_SOUND_FILE = 'alarm.wav'
FALLBACK_EAR = 0.24                # Fallback threshold used for detection

# Face mesh indices for landmarks used to compute EAR and MAR (MediaPipe 468 points)
# Left eye: [33, 160, 158, 133, 153, 144] (approx) - we'll pick the common 6 points
# Right eye: [362, 385, 387, 263, 373, 380]
LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]
# Mouth landmarks - using outer mouth points for better detection
# 61 = left corner, 291 = right corner
# 0 = upper lip top, 17 = lower lip bottom
# 13 = upper inner, 14 = lower inner
MOUTH_IDX = [61, 291, 0, 17]  # corners and top/bottom

# Utilities
def euclid(a, b):
    return np.linalg.norm(np.array(a) - np.array(b))

def ear_from_landmarks(landmarks, img_w, img_h, idx_list):
    pts = [(int(landmarks[i].x * img_w), int(landmarks[i].y * img_h)) for i in idx_list]
    # pts order: [p0, p1, p2, p3, p4, p5]
    A = euclid(pts[1], pts[5])
    B = euclid(pts[2], pts[4])
    C = euclid(pts[0], pts[3])
    if C == 0:
        return 0.0
    return (A + B) / (2.0 * C)

def mar_from_landmarks(landmarks, img_w, img_h, idx_list):
    """Calculate Mouth Aspect Ratio - focusing on vertical opening to detect yawns
    Yawning has significantly more vertical opening than talking"""
    # idx_list should be [left_corner, right_corner, top, bottom]
    pts = [(landmarks[i].x * img_w, landmarks[i].y * img_h) for i in idx_list]
    
    # Calculate mouth width (horizontal distance between corners)
    width = euclid(pts[0], pts[1])
    
    # Calculate vertical opening (distance between top and bottom of mouth)
    vertical_opening = euclid(pts[2], pts[3])
    
    if width == 0:
        return 0.0
    
    # MAR is the ratio of vertical opening to width
    # Yawning: high vertical opening relative to width
    # Talking: less vertical opening, more horizontal movement
    mar = vertical_opening / width
    
    return mar

def calculate_head_pitch(landmarks, img_w, img_h):
    """Calculate head pitch angle (up/down tilt) from face landmarks
    Returns: Negative angle when head is DOWN, positive when UP
    """
    # Key landmarks for pitch calculation
    # Nose tip: 1, Chin: 152, Forehead: 10
    nose_tip = np.array([landmarks[1].x, landmarks[1].y, landmarks[1].z])
    chin = np.array([landmarks[152].x, landmarks[152].y, landmarks[152].z])
    forehead = np.array([landmarks[10].x, landmarks[10].y, landmarks[10].z])
    
    # Calculate the vertical distance (Y-axis difference)
    # In image coordinates: Y increases downward
    # If chin Y > forehead Y by a lot more than normal, head is down
    vertical_dist = chin[1] - forehead[1]
    
    # Use nose Z-depth as indicator: more negative Z = closer to camera (head forward/down)
    # Normalize to get angle estimate
    # When head is down, nose Z becomes more negative
    pitch_angle = nose_tip[2] * 100  # Scale for degrees
    
    return pitch_angle


# Sound
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALARM_SOUND_PATH = os.path.join(SCRIPT_DIR, ALARM_SOUND_FILE)
pygame.mixer.init()
try:
    alarm_sound = pygame.mixer.Sound(ALARM_SOUND_PATH)
except pygame.error:
    print('[WARN] alarm.wav not found - sound disabled')
    alarm_sound = None

# MediaPipe init
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(static_image_mode=False,
                                  max_num_faces=1,
                                  refine_landmarks=True,
                                  min_detection_confidence=0.5,
                                  min_tracking_confidence=0.5)
mp_drawing = mp.solutions.drawing_utils

# State
calib_count = 0
calib_sum = 0.0
baseline_ear = None
baseline_ready = False

ear_ema = None
mar_ema = None

ear_counter = 0
mar_counter = 0
face_missing_counter = 0
head_down_counter = 0

# Event counters - track number of times each event occurred
eye_event_count = 0
yawn_event_count = 0
head_down_event_count = 0

# State tracking for event detection
was_eyes_closed = False
was_yawning = False
was_head_down = False

ALARM_ON = False
MISSING_ALARM_ON = False
HEAD_DOWN_ALARM_ON = False

# Open camera
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print('Could not open camera')
    exit(1)

print('[INFO] Starting MediaPipe Drowsiness Detection')
print("Press 'c' to recalibrate, 'r' to reset counters, 'q' to quit")
print("")
print("Detection modes:")
print("  - DROWSINESS ALERT: Eyes closed or yawning")
print("  - DRIVER DOWN ALERT: Head tilted down significantly")
print("  - DRIVER MISSING ALERT: No face detected")
print("")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    frame = cv2.flip(frame, 1)
    img_h, img_w = frame.shape[:2]
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = face_mesh.process(rgb)

    if results.multi_face_landmarks:
        face_missing_counter = 0
        # Stop missing alarm when face detected
        if MISSING_ALARM_ON:
            MISSING_ALARM_ON = False
            if alarm_sound:
                alarm_sound.stop()
        
        for face_landmarks in results.multi_face_landmarks:
            # Compute EAR and MAR
            left_ear = ear_from_landmarks(face_landmarks.landmark, img_w, img_h, LEFT_EYE_IDX)
            right_ear = ear_from_landmarks(face_landmarks.landmark, img_w, img_h, RIGHT_EYE_IDX)
            ear = (left_ear + right_ear) / 2.0
            mar = mar_from_landmarks(face_landmarks.landmark, img_w, img_h, MOUTH_IDX)
            
            # Calculate head pitch angle
            pitch_angle = calculate_head_pitch(face_landmarks.landmark, img_w, img_h)

            # Calibration - runs in background, doesn't block detection
            if not baseline_ready and calib_count < CALIBRATE_FRAMES:
                calib_sum += ear
                calib_count += 1
                cv2.putText(frame, f'Calibrating... ({calib_count}/{CALIBRATE_FRAMES})', (10,240), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0,255,255),1)
                if calib_count == CALIBRATE_FRAMES:
                    baseline_ear = calib_sum / float(calib_count)
                    baseline_ready = True
                    adaptive_thresh = max(0.12, baseline_ear * EAR_THRESHOLD_FACTOR)
                    print(f'[INFO] Calibration complete baseline_ear={baseline_ear:.3f} adaptive_thresh={adaptive_thresh:.3f}')

            # EMA smoothing
            if ear_ema is None:
                ear_ema = ear
            else:
                ear_ema = EAR_EMA_ALPHA * ear + (1 - EAR_EMA_ALPHA) * ear_ema
            if mar_ema is None:
                mar_ema = mar
            else:
                mar_ema = EAR_EMA_ALPHA * mar + (1 - EAR_EMA_ALPHA) * mar_ema

            use_ear = ear_ema if ear_ema is not None else ear
            use_mar = mar_ema if mar_ema is not None else mar

            # Determine threshold
            current_thresh = adaptive_thresh if baseline_ready else FALLBACK_EAR

            # Update counters
            if use_ear < current_thresh:
                ear_counter += 1
            else:
                ear_counter = 0
            if use_mar > MOUTH_AR_THRESH:
                mar_counter += 1
            else:
                mar_counter = 0
            
            # Head down detection (pitch angle check)
            # Negative pitch = head down, Positive pitch = head up
            if pitch_angle < HEAD_DOWN_PITCH_THRESH:
                head_down_counter += 1
            else:
                head_down_counter = 0

            # Priority 1: Check for drowsiness (eyes closed OR yawning)
            # Separated logic: eyes closed is independent from yawning
            eyes_closed_alert = (ear_counter >= EYE_AR_CONSEC_FRAMES)
            yawning_alert = (mar_counter >= YAWN_CONSEC_FRAMES)
            
            # Detect eye closure event (transition from open to closed and back to open)
            if eyes_closed_alert and not was_eyes_closed:
                was_eyes_closed = True  # Eyes just closed
            elif not eyes_closed_alert and was_eyes_closed:
                # Eyes just opened after being closed - increment event count
                eye_event_count += 1
                was_eyes_closed = False
                print(f"Eye closure event detected! Total count: {eye_event_count}")
            
            # Detect yawning event (transition from not yawning to yawning and back)
            if yawning_alert and not was_yawning:
                was_yawning = True  # Yawn started
            elif not yawning_alert and was_yawning:
                # Yawn ended - increment event count
                yawn_event_count += 1
                was_yawning = False
                print(f"Yawn event detected! Total count: {yawn_event_count}")
            
            should_drowsy_alert = eyes_closed_alert or yawning_alert
            
            # Priority 2: Check for head down
            should_head_down_alert = (head_down_counter >= HEAD_DOWN_CONSEC_FRAMES)
            
            # Detect head down event (transition from normal to head down and back)
            if should_head_down_alert and not was_head_down:
                was_head_down = True  # Head just went down
            elif not should_head_down_alert and was_head_down:
                # Head came back up - increment event count
                head_down_event_count += 1
                was_head_down = False
                print(f"Head down event detected! Total count: {head_down_event_count}")
            
            # Handle drowsiness alarm
            if should_drowsy_alert:
                if not ALARM_ON:
                    ALARM_ON = True
                    if eyes_closed_alert:
                        print("DROWSINESS DETECTED - Eyes closed!")
                    if yawning_alert:
                        print("DROWSINESS DETECTED - Yawning detected!")
                    if alarm_sound and not HEAD_DOWN_ALARM_ON:
                        alarm_sound.play(-1)
                
                # Show specific alert message
                if eyes_closed_alert:
                    cv2.putText(frame, 'DROWSINESS: EYES CLOSED!', (10,60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
                elif yawning_alert:
                    cv2.putText(frame, 'DROWSINESS: YAWNING!', (10,60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
            else:
                if ALARM_ON:
                    ALARM_ON = False
                    if alarm_sound and not HEAD_DOWN_ALARM_ON:
                        alarm_sound.stop()
            
            # Handle head down alarm (separate from drowsiness)
            if should_head_down_alert:
                if not HEAD_DOWN_ALARM_ON:
                    HEAD_DOWN_ALARM_ON = True
                    print("DRIVER DOWN DETECTED - Head tilted down!")
                    if alarm_sound and not ALARM_ON:
                        alarm_sound.play(-1)
                cv2.putText(frame, 'DRIVER DOWN ALERT!', (10,90), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
            else:
                if HEAD_DOWN_ALARM_ON:
                    HEAD_DOWN_ALARM_ON = False
                    if alarm_sound and not ALARM_ON:
                        alarm_sound.stop()

            # Draw mesh and small UI
            mp_drawing.draw_landmarks(frame, face_landmarks, mp_face_mesh.FACEMESH_TESSELATION,
                                      mp_drawing.DrawingSpec(color=(0,255,255), thickness=1, circle_radius=1),
                                      mp_drawing.DrawingSpec(color=(0,200,200), thickness=1))

            cv2.putText(frame, f'EAR: {use_ear:.2f} (Thresh: {current_thresh:.2f})', (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
            cv2.putText(frame, f'MAR: {use_mar:.2f} (Thresh: {MOUTH_AR_THRESH:.2f})', (10,120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2)
            cv2.putText(frame, f'Pitch: {pitch_angle:.1f}deg (Thresh: {HEAD_DOWN_PITCH_THRESH:.1f})', (10,150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)
            
            # Show event counters in red with larger text
            cv2.putText(frame, f'Eye Closures: {eye_event_count}', (10,180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
            cv2.putText(frame, f'Yawns: {yawn_event_count}', (10,210), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
            #cv2.putText(frame, f'Head Down Events: {head_down_event_count}', (10,240), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

    else:
        # No face detected
        # Stop drowsiness and head down alarms when no face
        if ALARM_ON:
            ALARM_ON = False
            if alarm_sound and not MISSING_ALARM_ON and not HEAD_DOWN_ALARM_ON:
                alarm_sound.stop()
        if HEAD_DOWN_ALARM_ON:
            HEAD_DOWN_ALARM_ON = False
            if alarm_sound and not MISSING_ALARM_ON and not ALARM_ON:
                alarm_sound.stop()
        
        ear_counter = 0
        mar_counter = 0
        head_down_counter = 0
        ear_ema = None
        mar_ema = None
        
        # Reset state tracking when face is missing
        was_eyes_closed = False
        was_yawning = False
        was_head_down = False
        
        face_missing_counter += 1
        if face_missing_counter >= FACE_MISSING_CONSEC_FRAMES:
            if not MISSING_ALARM_ON:
                MISSING_ALARM_ON = True
                print("DRIVER MISSING - No face detected!")
                if alarm_sound:
                    alarm_sound.play(-1)
            cv2.putText(frame, 'DRIVER MISSING ALERT!', (10,60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
        else:
            if MISSING_ALARM_ON:
                MISSING_ALARM_ON = False
                if alarm_sound:
                    alarm_sound.stop()

    cv2.imshow('Drowsiness - MediaPipe', frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('c'):
        print('[INFO] Manual recalibration')
        calib_count = 0
        calib_sum = 0.0
        baseline_ready = False
    if key == ord('r'):
        print('[INFO] Resetting counters')
        ear_counter = 0
        mar_counter = 0
        face_missing_counter = 0
        head_down_counter = 0
        ear_ema = None
        mar_ema = None
        
        # Reset event counters and state tracking
        eye_event_count = 0
        yawn_event_count = 0
        head_down_event_count = 0
        was_eyes_closed = False
        was_yawning = False
        was_head_down = False
        
        ALARM_ON = False
        MISSING_ALARM_ON = False
        HEAD_DOWN_ALARM_ON = False
        if alarm_sound:
            alarm_sound.stop()
    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
if alarm_sound:
    pygame.mixer.quit()
face_mesh.close()

print('Exiting')
