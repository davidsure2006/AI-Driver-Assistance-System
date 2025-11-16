import cv2
import dlib
from scipy.spatial import distance as dist
from imutils import face_utils
import os
import pygame
import numpy as np
import time
from collections import deque

# --- Visualization Colors ---
# Teal/Cyan for the mesh lines and points
MESH_COLOR = (255, 200, 0) # BGR: Bright Cyan/Teal
BOX_COLOR = (0, 0, 255) # BGR: Red for the bounding box (for contrast)

# --- Mesh Drawing Function (Custom Dlib 68-Point Mesh) ---
def draw_dlib_mesh(frame, shape):
    """Draws the 68-point facial mesh, including points and key lines."""
    # Draw all 68 individual points as prominent circles
    for (x_p, y_p) in shape:
        cv2.circle(frame, (x_p, y_p), 2, MESH_COLOR, -1) 

    # 1. Connect the standard feature outlines (Sequential points)
    
    # Jawline (0-16)
    for i in range(0, 16):
        cv2.line(frame, tuple(shape[i]), tuple(shape[i+1]), MESH_COLOR, 1)

    # Eyebrows (17-21 for left, 22-26 for right)
    for i in range(17, 21):
        cv2.line(frame, tuple(shape[i]), tuple(shape[i+1]), MESH_COLOR, 1)
    for i in range(22, 26):
        cv2.line(frame, tuple(shape[i]), tuple(shape[i+1]), MESH_COLOR, 1)

    # Eyes (36-41 for left, 42-47 for right) - Closed loop
    cv2.drawContours(frame, [np.array(shape[36:42])], -1, MESH_COLOR, 1)
    cv2.drawContours(frame, [np.array(shape[42:48])], -1, MESH_COLOR, 1)

    # Mouth (48-67) - Inner and Outer loops
    cv2.drawContours(frame, [np.array(shape[48:60])], -1, MESH_COLOR, 1)
    cv2.drawContours(frame, [np.array(shape[60:68])], -1, MESH_COLOR, 1)
    
    # Nose (27-35)
    for i in range(27, 30):
        cv2.line(frame, tuple(shape[i]), tuple(shape[i+1]), MESH_COLOR, 1)
    for i in range(31, 35):
        cv2.line(frame, tuple(shape[i]), tuple(shape[i+1]), MESH_COLOR, 1)
    cv2.line(frame, tuple(shape[30]), tuple(shape[35]), MESH_COLOR, 1) 

    # 2. Add Strategic Lines for the 'Triangulated Mesh' Look
    
    # Vertical connections (Nose/Eyes to Jaw/Chin)
    cv2.line(frame, tuple(shape[30]), tuple(shape[8]), MESH_COLOR, 1) # Nose to Chin
    cv2.line(frame, tuple(shape[36]), tuple(shape[3]), MESH_COLOR, 1) # Left Eye to Cheek
    cv2.line(frame, tuple(shape[45]), tuple(shape[13]), MESH_COLOR, 1) # Right Eye to Cheek

    # Horizontal connections (Across Nose/Eyes)
    cv2.line(frame, tuple(shape[36]), tuple(shape[45]), MESH_COLOR, 1) # Across Eyes
    cv2.line(frame, tuple(shape[31]), tuple(shape[35]), MESH_COLOR, 1) # Across Nose Bottom
    cv2.line(frame, tuple(shape[39]), tuple(shape[42]), MESH_COLOR, 1) # Across Eye centers

    # Diagonal connections (Eyes to Nose Bridge)
    cv2.line(frame, tuple(shape[39]), tuple(shape[30]), MESH_COLOR, 1)
    cv2.line(frame, tuple(shape[42]), tuple(shape[30]), MESH_COLOR, 1)


# Function to calculate Eye Aspect Ratio (EAR)
def eye_aspect_ratio(eye):
    """Calculates the Eye Aspect Ratio (EAR) based on Dlib points."""
    # The formula calculates the ratio of vertical eye distances to the horizontal eye distance.
    # A, B are vertical distances (e.g., inner corner to outer corner of the eye)
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    # C is the horizontal distance (between the horizontal end points of the eye)
    C = dist.euclidean(eye[0], eye[3])
    ear = (A + B) / (2.0 * C)
    return ear

# Function to calculate Mouth Aspect Ratio (MAR)
def mouth_aspect_ratio(mouth):
    """Calculates the Mouth Aspect Ratio (MAR) based on Dlib points."""
    # A, B, C are vertical distances across the mouth
    A = dist.euclidean(mouth[1], mouth[7])
    B = dist.euclidean(mouth[2], mouth[6])
    C = dist.euclidean(mouth[3], mouth[5])
    # D is the horizontal distance (width of the mouth)
    D = dist.euclidean(mouth[0], mouth[4])
    mar = (A + B + C) / (2.0 * D)
    return mar

# Define constants
# Detection parameters
EYE_AR_THRESH = 0.25            # fallback threshold (used if calibration not available)
EYE_AR_CONSEC_FRAMES = 18      # frames of sustained low EAR before alarm
MOUTH_AR_THRESH = 2.0
YAWN_CONSEC_FRAMES = 20

# Smoothing / calibration
CALIBRATE_FRAMES = 120         # number of frames at startup to calibrate baseline EAR
EAR_THRESHOLD_FACTOR = 0.60    # threshold = baseline_ear * EAR_THRESHOLD_FACTOR
EAR_EMA_ALPHA = 0.35           # smoothing factor for EAR exponential moving average
EAR_HYSTERESIS = 0.04          # hysteresis margin to avoid alarm flapping

ALARM_ON = False
MISSING_ALARM_ON = False
FACE_MISSING_CONSEC_FRAMES = 30
ALARM_SOUND_FILE = "alarm.wav"

# Get the directory of the script to find the required files
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALARM_SOUND_PATH = os.path.join(SCRIPT_DIR, ALARM_SOUND_FILE)
PREDICTOR_PATH = os.path.join(SCRIPT_DIR, "shape_predictor_68_face_landmarks.dat")

# Initialize pygame mixer
# Initialize pygame mixer (sound)
pygame.mixer.init()

# Load the alarm sound
try:
    print("[INFO] Loading alarm sound...")
    alarm_sound = pygame.mixer.Sound(ALARM_SOUND_PATH)
except pygame.error as e:
    print(f"Warning: Alarm sound file not found or could not be loaded: {e}")
    alarm_sound = None

# Initialize dlib's face detector and then create the facial landmark predictor
try:
    print("[INFO] loading facial landmark predictor...")
    detector = dlib.get_frontal_face_detector()
    predictor = dlib.shape_predictor(PREDICTOR_PATH)
except RuntimeError as e:
    print(f"Error: {e}")
    print(f"Make sure '{os.path.basename(PREDICTOR_PATH)}' is in the same directory as the script.")
    exit()

# Grab the indexes of the facial landmarks for the eyes and mouth
(lStart, lEnd) = face_utils.FACIAL_LANDMARKS_IDXS["left_eye"]
(rStart, rEnd) = face_utils.FACIAL_LANDMARKS_IDXS["right_eye"]
(mStart, mEnd) = face_utils.FACIAL_LANDMARKS_IDXS["mouth"]

# Start the video stream

print("[INFO] starting video stream...")
vs = cv2.VideoCapture(0)
ear_counter = 0
mar_counter = 0
face_missing_counter = 0 # Counter for missing frames

# Calibration state
calib_count = 0
calib_sum = 0.0
baseline_ear = None
baseline_ready = False

# Smoothing state
ear_ema = None
mar_ema = None

# Recovery counters (hysteresis)
ear_recover_counter = 0
EAR_RECOVER_FRAMES = 10

while True:
    ret, frame = vs.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    rects = detector(gray, 0)

    # --- NEAREST FACE SELECTION LOGIC ---
    nearest_face_rect = None
    max_area = 0
    for rect in rects:
        current_area = rect.width() * rect.height()
        if current_area > max_area:
            max_area = current_area
            nearest_face_rect = rect

    ear = 0.0
    mar = 0.0

    # If a face is detected, update metrics and smoothing
    if nearest_face_rect is not None:
        # Reset missing face counter and stop missing alarm
        face_missing_counter = 0
        if MISSING_ALARM_ON:
            MISSING_ALARM_ON = False
            if alarm_sound:
                alarm_sound.stop()

        (x, y, w, h) = face_utils.rect_to_bb(nearest_face_rect)
        cv2.rectangle(frame, (x, y), (x + w, y + h), BOX_COLOR, 2)

        shape = predictor(gray, nearest_face_rect)
        shape = face_utils.shape_to_np(shape)

        # Draw the custom Dlib-based mesh
        draw_dlib_mesh(frame, shape)

        # Compute EAR and MAR from landmarks
        leftEye = shape[lStart:lEnd]
        rightEye = shape[rStart:rEnd]
        leftEAR = eye_aspect_ratio(leftEye)
        rightEAR = eye_aspect_ratio(rightEye)
        ear = (leftEAR + rightEAR) / 2.0

        mouth = shape[mStart:mEnd]
        mar = mouth_aspect_ratio(mouth)

        # Calibration phase: build baseline EAR
        if not baseline_ready and calib_count < CALIBRATE_FRAMES:
            calib_sum += ear
            calib_count += 1
            cv2.putText(frame, f"Calibrating... ({calib_count}/{CALIBRATE_FRAMES})", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            if calib_count == CALIBRATE_FRAMES:
                baseline_ear = calib_sum / float(calib_count)
                baseline_ready = True
                # set adaptive threshold
                EYE_AR_THRESH = max(0.12, baseline_ear * EAR_THRESHOLD_FACTOR)
                print(f"[INFO] Calibration complete. baseline_ear={baseline_ear:.3f}, adaptive_threshold={EYE_AR_THRESH:.3f}")

        # Allow manual recalibration by pressing 'c' (handled in keypress below)

        # Update EMA smoothing
        if ear_ema is None:
            ear_ema = ear
        else:
            ear_ema = EAR_EMA_ALPHA * ear + (1 - EAR_EMA_ALPHA) * ear_ema

        if mar_ema is None:
            mar_ema = mar
        else:
            mar_ema = EAR_EMA_ALPHA * mar + (1 - EAR_EMA_ALPHA) * mar_ema

        # Use smoothed EAR for detection
        use_ear = ear_ema if ear_ema is not None else ear
        use_mar = mar_ema if mar_ema is not None else mar

        # Update counters based on smoothed values and adaptive threshold
        current_threshold = EYE_AR_THRESH
        if use_ear < current_threshold:
            ear_counter += 1
            ear_recover_counter = 0
        else:
            ear_recover_counter += 1
            ear_counter = 0

        if use_mar > MOUTH_AR_THRESH:
            mar_counter += 1
        else:
            mar_counter = 0

        # Combined drowsiness logic with hysteresis
        should_alert = (ear_counter >= EYE_AR_CONSEC_FRAMES) or (mar_counter >= YAWN_CONSEC_FRAMES) or (use_ear < current_threshold and use_mar > MOUTH_AR_THRESH)

        if should_alert:
            if not ALARM_ON:
                ALARM_ON = True
                print("Drowsiness detected! Playing sound...")
                if alarm_sound:
                    alarm_sound.play(-1)
            cv2.putText(frame, "DROWSINESS ALERT!", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        else:
            # require stable recovery before stopping alarm (hysteresis)
            if ALARM_ON and ear_recover_counter >= EAR_RECOVER_FRAMES:
                ALARM_ON = False
                if alarm_sound:
                    alarm_sound.stop()

        # Reset missing-driver counters when face present


    # Display metrics on subsequent lines
    display_ear = ear_ema if ear_ema is not None else ear
    display_mar = mar_ema if mar_ema is not None else mar
    cv2.putText(frame, "EAR: {:.2f}".format(display_ear), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    cv2.putText(frame, "MAR: {:.2f}".format(display_mar), (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.putText(frame, "Driver Down/Missing Count: {}".format(face_missing_counter), (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    if baseline_ready:
        cv2.putText(frame, f"Calibrated threshold: {EYE_AR_THRESH:.2f}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)
    
    cv2.imshow("Drowsiness Detection System (Nearest Face Mesh)", frame)
    key = cv2.waitKey(1) & 0xFF
    # Allow manual recalibration: press 'c' to recalibrate baseline EAR
    if key == ord('c'):
        print("Manual recalibration started")
        calib_count = 0
        calib_sum = 0.0
        baseline_ready = False
    if key == ord('q'):
        break

cv2.destroyAllWindows()
vs.release()
pygame.mixer.quit()