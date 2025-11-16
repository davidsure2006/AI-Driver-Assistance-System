import cv2
import dlib
from scipy.spatial import distance as dist
from imutils import face_utils
import os
import pygame

# Function to calculate Eye Aspect Ratio (EAR)
def eye_aspect_ratio(eye):
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    ear = (A + B) / (2.0 * C)
    return ear

# Function to calculate Mouth Aspect Ratio (MAR)
def mouth_aspect_ratio(mouth):
    A = dist.euclidean(mouth[1], mouth[7])
    B = dist.euclidean(mouth[2], mouth[6])
    C = dist.euclidean(mouth[3], mouth[5])
    D = dist.euclidean(mouth[0], mouth[4])
    mar = (A + B + C) / (2.0 * D)
    return mar

# Define constants
EYE_AR_THRESH = 0.25
EYE_AR_CONSEC_FRAMES = 18  # Reduced value for faster detection
MOUTH_AR_THRESH = 2.0
YAWN_CONSEC_FRAMES = 20
HEAD_NOD_THRESH = 15
ALARM_ON = False
ALARM_SOUND_FILE = "alarm.wav"

# Get the directory of the script to find the required files
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ALARM_SOUND_PATH = os.path.join(SCRIPT_DIR, ALARM_SOUND_FILE)
PREDICTOR_PATH = os.path.join(SCRIPT_DIR, "shape_predictor_68_face_landmarks.dat")

# Initialize pygame mixer
pygame.mixer.init()

# Load the alarm sound
try:
    print("[INFO] Loading alarm sound...")
    alarm_sound = pygame.mixer.Sound(ALARM_SOUND_PATH)
except pygame.error as e:
    print(f"Error: Alarm sound file not found or could not be loaded: {e}")
    exit()

# Initialize dlib's face detector and then create the facial landmark predictor
try:
    print("[INFO] loading facial landmark predictor...")
    detector = dlib.get_frontal_face_detector()
    # Up-sampling to detect smaller or distant faces better
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
head_nod_counter = 0
prev_nose_y = None

while True:
    ret, frame = vs.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    rects = detector(gray, 0)
    
    ear = 0.0
    mar = 0.0

    for rect in rects:
        (x, y, w, h) = face_utils.rect_to_bb(rect)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
        
        shape = predictor(gray, rect)
        shape = face_utils.shape_to_np(shape)
        
        # Eye Aspect Ratio calculation
        leftEye = shape[lStart:lEnd]
        rightEye = shape[rStart:rEnd]
        leftEAR = eye_aspect_ratio(leftEye)
        rightEAR = eye_aspect_ratio(rightEye)
        ear = (leftEAR + rightEAR) / 2.0
        
        # Mouth Aspect Ratio calculation
        mouth = shape[mStart:mEnd]
        mar = mouth_aspect_ratio(mouth)

        # Head Nod detection
        nose_tip = shape[30]
        if prev_nose_y is not None:
            if nose_tip[1] - prev_nose_y > HEAD_NOD_THRESH:
                head_nod_counter += 1
            else:
                head_nod_counter = 0
        prev_nose_y = nose_tip[1]
        
        # Draw all 68 facial landmarks
        for (x_p, y_p) in shape:
            cv2.circle(frame, (x_p, y_p), 1, (0, 255, 255), -1)

        # Update counters
        if ear < EYE_AR_THRESH:
            ear_counter += 1
        else:
            ear_counter = 0
        
        if mar > MOUTH_AR_THRESH:
            mar_counter += 1
        else:
            mar_counter = 0
        
        # Trigger alarm based on combined drowsiness logic
        if (ear_counter >= EYE_AR_CONSEC_FRAMES) or \
           (mar_counter >= YAWN_CONSEC_FRAMES) or \
           (head_nod_counter >= 3) or \
           (ear < EYE_AR_THRESH and mar > MOUTH_AR_THRESH):
            
            if not ALARM_ON:
                ALARM_ON = True
                print("Drowsiness detected! Playing sound...")
                alarm_sound.play(-1)
            cv2.putText(frame, "DROWSINESS ALERT!", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        else:
            if ALARM_ON:
                ALARM_ON = False
                alarm_sound.stop()
    
    cv2.putText(frame, "EAR: {:.2f}".format(ear), (300, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
    cv2.putText(frame, "MAR: {:.2f}".format(mar), (300, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    cv2.putText(frame, "Nod Count: {}".format(head_nod_counter), (300, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
    
    cv2.imshow("Drowsiness Detection System", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break

cv2.destroyAllWindows()
vs.release()
pygame.mixer.quit()