"""
Integrated Driver Monitoring System
- Runs drowsiness detection and lane detection simultaneously
- Controls vehicle speed based on driver state
- Shared alarm system

Driver States:
  NORMAL: Lane detection runs at normal speed
  DROWSY: Lane detection slows down (50% speed)
  DRIVER_DOWN/MISSING: Lane detection stops completely
"""

import cv2
import mediapipe as mp
import numpy as np
import pygame
import os
import threading
import time
import signal
import sys
from queue import Queue

# ==================== DROWSINESS DETECTION CONFIG ====================
CALIBRATE_FRAMES = 60  # Reduced from 120 to 60 frames (~2 seconds at 30 FPS)
EAR_THRESHOLD_FACTOR = 0.85
EAR_EMA_ALPHA = 0.35
EYE_AR_CONSEC_FRAMES = 8
MOUTH_AR_THRESH = 0.75
YAWN_CONSEC_FRAMES = 20
FACE_MISSING_CONSEC_FRAMES = 30
HEAD_DOWN_PITCH_THRESH = -10.0
HEAD_DOWN_CONSEC_FRAMES = 10
FALLBACK_EAR = 0.30

# Face mesh indices
LEFT_EYE_IDX = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_IDX = [362, 385, 387, 263, 373, 380]
MOUTH_IDX = [61, 291, 0, 17]

# ==================== SHARED STATE ====================
class DriverState:
    NORMAL = 0
    DROWSY = 1
    DRIVER_DOWN = 2
    DRIVER_MISSING = 3

driver_state = DriverState.NORMAL
state_lock = threading.Lock()
alarm_sound = None
system_running = True  # Global flag to stop all threads
current_speed = 100.0  # Current vehicle speed (0-100%)
driver_frame = None  # Shared frame from driver monitoring
driver_frame_lock = threading.Lock()  # Lock for driver frame

# ==================== UTILITY FUNCTIONS ====================
def euclid(a, b):
    return np.linalg.norm(np.array(a) - np.array(b))

def ear_from_landmarks(landmarks, img_w, img_h, idx_list):
    pts = [(int(landmarks[i].x * img_w), int(landmarks[i].y * img_h)) for i in idx_list]
    A = euclid(pts[1], pts[5])
    B = euclid(pts[2], pts[4])
    C = euclid(pts[0], pts[3])
    if C == 0:
        return 0.0
    return (A + B) / (2.0 * C)

def mar_from_landmarks(landmarks, img_w, img_h, idx_list):
    pts = [(landmarks[i].x * img_w, landmarks[i].y * img_h) for i in idx_list]
    width = euclid(pts[0], pts[1])
    vertical_opening = euclid(pts[2], pts[3])
    if width == 0:
        return 0.0
    return vertical_opening / width

def calculate_head_pitch(landmarks, img_w, img_h):
    nose_tip = np.array([landmarks[1].x, landmarks[1].y, landmarks[1].z])
    pitch_angle = nose_tip[2] * 100
    return pitch_angle

# ==================== DROWSINESS DETECTION THREAD ====================
def drowsiness_detection_thread():
    global driver_state, alarm_sound, system_running, driver_frame
    
    # Initialize pygame
    pygame.mixer.init()
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    ALARM_SOUND_PATH = os.path.join(SCRIPT_DIR, "Facerecognition", "alarm.wav")
    try:
        alarm_sound = pygame.mixer.Sound(ALARM_SOUND_PATH)
    except:
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
    
    # State variables
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
    
    # Event counters (persist across frames)
    total_eye_closures = 0
    total_yawns = 0
    eye_closure_triggered = False
    yawn_triggered = False
    
    # Open camera
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print('Could not open camera for drowsiness detection')
        system_running = False
        return
    
    print('[INFO] Drowsiness Detection Started')
    
    while system_running:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame = cv2.flip(frame, 1)
        img_h, img_w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = face_mesh.process(rgb)
        
        if results.multi_face_landmarks:
            face_missing_counter = 0
            
            for face_landmarks in results.multi_face_landmarks:
                # Calculate metrics
                left_ear = ear_from_landmarks(face_landmarks.landmark, img_w, img_h, LEFT_EYE_IDX)
                right_ear = ear_from_landmarks(face_landmarks.landmark, img_w, img_h, RIGHT_EYE_IDX)
                ear = (left_ear + right_ear) / 2.0
                mar = mar_from_landmarks(face_landmarks.landmark, img_w, img_h, MOUTH_IDX)
                pitch_angle = calculate_head_pitch(face_landmarks.landmark, img_w, img_h)
                
                # Calibration
                if not baseline_ready and calib_count < CALIBRATE_FRAMES:
                    calib_sum += ear
                    calib_count += 1
                    
                    # Set state to NORMAL during calibration
                    with state_lock:
                        driver_state = DriverState.NORMAL
                    
                    # Add calibration overlay (will be shown in main thread)
                    cv2.rectangle(frame, (5, 5), (frame.shape[1]-5, 100), (0, 0, 0), -1)
                    cv2.rectangle(frame, (5, 5), (frame.shape[1]-5, 100), (0, 255, 255), 3)
                    cv2.putText(frame, f'CALIBRATING... ({calib_count}/{CALIBRATE_FRAMES})', 
                               (10,35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,255), 2)
                    cv2.putText(frame, 'Look straight ahead - Keep eyes open', 
                               (10,70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,255), 2)
                    
                    if calib_count == CALIBRATE_FRAMES:
                        baseline_ear = calib_sum / float(calib_count)
                        baseline_ready = True
                        adaptive_thresh = max(0.12, baseline_ear * EAR_THRESHOLD_FACTOR)
                        print(f'[INFO] Calibration complete baseline_ear={baseline_ear:.3f}')
                    
                    # Share driver frame during calibration
                    with driver_frame_lock:
                        driver_frame = frame.copy()
                    
                    # Skip detection during calibration - no GUI operations in worker thread
                    if not system_running:
                        break
                    continue  # Skip rest of loop during calibration
                
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
                current_thresh = adaptive_thresh if baseline_ready else FALLBACK_EAR
                
                # Update counters
                if use_ear < current_thresh:
                    ear_counter += 1
                else:
                    # Reset on opening
                    if ear_counter >= EYE_AR_CONSEC_FRAMES and not eye_closure_triggered:
                        total_eye_closures += 1
                        eye_closure_triggered = True
                        print(f'[EVENT] Eye closure detected! Total: {total_eye_closures}')
                    ear_counter = 0
                    eye_closure_triggered = False
                
                if use_mar > MOUTH_AR_THRESH:
                    mar_counter += 1
                else:
                    # Reset on mouth close
                    if mar_counter >= YAWN_CONSEC_FRAMES and not yawn_triggered:
                        total_yawns += 1
                        yawn_triggered = True
                        print(f'[EVENT] Yawn detected! Total: {total_yawns}')
                    mar_counter = 0
                    yawn_triggered = False
                
                if pitch_angle < HEAD_DOWN_PITCH_THRESH:
                    head_down_counter += 1
                else:
                    head_down_counter = 0
                
                # Determine driver state
                eyes_closed = (ear_counter >= EYE_AR_CONSEC_FRAMES)
                yawning = (mar_counter >= YAWN_CONSEC_FRAMES)
                head_down = (head_down_counter >= HEAD_DOWN_CONSEC_FRAMES)
                
                with state_lock:
                    if head_down:
                        driver_state = DriverState.DRIVER_DOWN
                        if alarm_sound:
                            alarm_sound.play(-1)
                        cv2.putText(frame, 'DRIVER DOWN/MISSING ALERT!', (10,60), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
                        cv2.putText(frame, 'CAR STOPPED', (10,90), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
                    elif eyes_closed or yawning:
                        driver_state = DriverState.DROWSY
                        if alarm_sound:
                            alarm_sound.play(-1)
                        cv2.putText(frame, 'DROWSINESS ALERT!', (10,60), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
                        cv2.putText(frame, 'CAR SLOWING DOWN', (10,90), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,165,0), 2)
                    else:
                        driver_state = DriverState.NORMAL
                        if alarm_sound:
                            alarm_sound.stop()
                        cv2.putText(frame, 'NORMAL DRIVING', (10,60), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,255,0), 2)
                
                # Draw face mesh
                mp_drawing.draw_landmarks(frame, face_landmarks, mp_face_mesh.FACEMESH_TESSELATION,
                                         mp_drawing.DrawingSpec(color=(0,255,255), thickness=1, circle_radius=1),
                                         mp_drawing.DrawingSpec(color=(0,200,200), thickness=1))
                
                # Display metrics
                cv2.putText(frame, f'EAR: {use_ear:.2f}', (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,0), 2)
                cv2.putText(frame, f'MAR: {use_mar:.2f}', (10,120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2)
                cv2.putText(frame, f'Pitch: {pitch_angle:.1f}deg', (10,150), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,0), 2)
                
                # Display event counters
                cv2.putText(frame, f'Eye Closures: {total_eye_closures}', (10,180), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,100,100), 2)
                cv2.putText(frame, f'Yawns: {total_yawns}', (10,210), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,200,100), 2)
        
        else:
            # No face detected
            ear_counter = 0
            mar_counter = 0
            head_down_counter = 0
            ear_ema = None
            mar_ema = None
            face_missing_counter += 1
            
            if face_missing_counter >= FACE_MISSING_CONSEC_FRAMES:
                with state_lock:
                    driver_state = DriverState.DRIVER_MISSING
                    if alarm_sound:
                        alarm_sound.play(-1)
                cv2.putText(frame, 'DRIVER DOWN/MISSING ALERT!', (10,60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2)
                cv2.putText(frame, 'CAR STOPPED', (10,90), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
            else:
                with state_lock:
                    if driver_state == DriverState.DRIVER_MISSING:
                        driver_state = DriverState.NORMAL
                        if alarm_sound:
                            alarm_sound.stop()
        
        # Share driver frame for display in lane detection window
        with driver_frame_lock:
            driver_frame = frame.copy()
        
        # Don't show separate window - will be overlaid on lane detection
        # Don't call cv2.waitKey here - it will be called in main thread
        
        # Also check if system was stopped from other thread
        if not system_running:
            print("[INFO] Drowsiness Detection - system shutdown signal received")
            break
    
    # Cleanup
    print("[INFO] Drowsiness Detection - starting cleanup...")
    cap.release()
    # No separate window to destroy
    if alarm_sound:
        alarm_sound.stop()
        pygame.mixer.quit()
    face_mesh.close()
    print("[INFO] Drowsiness Detection Stopped")

# Global for combined display frame
combined_frame = None
combined_frame_lock = threading.Lock()

# ==================== LANE DETECTION THREAD ====================
def lane_detection_thread():
    global driver_state, system_running, current_speed, driver_frame, combined_frame, combined_frame_lock
    
    # Use the processed output video with lane detection
    video_path = os.path.join("Road Lane detection", "Advanced-Lane-Lines", "output_videos", "project_video_output.mp4")
    if not os.path.exists(video_path):
        print(f'[ERROR] Video not found: {video_path}')
        system_running = False
        return
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print('[ERROR] Could not open lane video')
        system_running = False
        return
    
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    print('[INFO] Lane Detection Started')
    print(f'[INFO] Video: {total_frames} frames at {fps} FPS')
    
    frame_count = 0
    last_state = DriverState.NORMAL
    frames_in_state = 0
    drowsy_delay_frames = int(1.5 * fps)  # 1.5 seconds delay at video FPS (25 FPS = 37-38 frames)
    max_speed_kmh = 120.0  # Maximum speed in km/h
    
    while system_running:
        # Check if system is still running
        if not system_running:
            break
            
        current_state = None
        with state_lock:
            current_state = driver_state
        
        # Track state changes
        if current_state != last_state:
            last_state = current_state
            frames_in_state = 0
        else:
            frames_in_state += 1
        
        # Gradual speed adjustment based on driver state
        target_speed = 100.0
        
        if current_state == DriverState.DRIVER_DOWN or current_state == DriverState.DRIVER_MISSING:
            # Quick deceleration: 10% per 3 frames
            target_speed = 0.0
            if current_speed > target_speed:
                if frames_in_state % 3 == 0:  # Every 3 frames
                    current_speed = max(0.0, current_speed - 10.0)
            elif current_speed < target_speed:
                if frames_in_state % 3 == 0:  # Match deceleration rate for acceleration
                    current_speed = min(100.0, current_speed + 10.0)
            speed_text = f"EMERGENCY STOP ({int(current_speed)}%)"
            speed_color = (0, 0, 255)  # Red
            
        elif current_state == DriverState.DROWSY:
            # Wait 1.5 seconds before starting to slow down
            if frames_in_state < drowsy_delay_frames:
                # Still in warning period - alarm sounds but no speed reduction yet
                speed_text = f"DROWSINESS WARNING! ({int(current_speed)}%)"
                speed_color = (0, 165, 255)  # Orange
            else:
                # After 1.5 seconds, start gradual deceleration: 10% per 10 frames
                target_speed = 0.0
                adjusted_frames = frames_in_state - drowsy_delay_frames
                if current_speed > target_speed:
                    if adjusted_frames % 10 == 0:  # Every 10 frames after delay
                        current_speed = max(target_speed, current_speed - 10.0)
                elif current_speed < target_speed:
                    if adjusted_frames % 10 == 0:  # Match deceleration rate for acceleration
                        current_speed = min(100.0, current_speed + 10.0)
                
                # Show different text based on speed
                if current_speed == 0:
                    speed_text = f"STOPPED - DROWSY ({int(current_speed)}%)"
                else:
                    speed_text = f"SLOWING DOWN ({int(current_speed)}%)"
                speed_color = (0, 165, 255)  # Orange
            
        else:  # NORMAL
            # Accelerate back to normal - match fastest deceleration rate (10% per 3 frames)
            target_speed = 100.0
            if current_speed < target_speed:
                if frames_in_state % 3 == 0:  # Every 3 frames - same as emergency deceleration
                    current_speed = min(100.0, current_speed + 10.0)
            speed_text = f"NORMAL SPEED ({int(current_speed)}%)"
            speed_color = (0, 255, 0)  # Green
        
        # Calculate wait time based on current speed
        if current_speed <= 0:
            wait_time = 100  # Stopped
        else:
            # Speed affects frame delay
            speed_factor = current_speed / 100.0
            wait_time = max(1, int((1000 / fps) / speed_factor))
        
        # Only advance frame if moving
        if current_speed > 0:
            ret, frame = cap.read()
            if not ret:
                # Loop video
                cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                frame_count = 0
                continue
            frame_count += 1
        else:
            # Frozen frame - just get current frame without advancing
            current_pos = cap.get(cv2.CAP_PROP_POS_FRAMES)
            ret, frame = cap.read()
            if ret:
                cap.set(cv2.CAP_PROP_POS_FRAMES, current_pos)  # Reset to same position
        
        if frame is not None:
            frame_h, frame_w = frame.shape[:2]
            
            # Add driver monitor overlay on TOP-LEFT
            driver_monitor_width = int(frame_w * 0.35)  # 35% of frame width
            driver_monitor_height = int(frame_h * 0.55)  # Increased from 45% to 60% of frame height
            
            # Position: Moved down from top
            dm_x = 10
            dm_y = 50  # Moved down from 10 to 50
            
            with driver_frame_lock:
                if driver_frame is not None:
                    # Resize driver frame for overlay
                    resized_driver = cv2.resize(driver_frame, (driver_monitor_width, driver_monitor_height))
                    
                    # Add label above driver monitor (no background)
                    cv2.putText(frame, 'Driver Monitor', 
                               (dm_x + 10, dm_y - 8), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    
                    # Add border
                    cv2.rectangle(frame, (dm_x-3, dm_y-3), 
                                (dm_x + driver_monitor_width + 3, dm_y + driver_monitor_height + 3), 
                                (255, 255, 255), 3)
                    
                    # Overlay driver monitor
                    frame[dm_y:dm_y+driver_monitor_height, dm_x:dm_x+driver_monitor_width] = resized_driver
            
            # Calculate real speed in km/h
            current_speed_kmh = (current_speed / 100.0) * max_speed_kmh
            
            # Display driver state
            state_names = {
                DriverState.NORMAL: "NORMAL",
                DriverState.DROWSY: "DROWSY",
                DriverState.DRIVER_DOWN: "DRIVER DOWN",
                DriverState.DRIVER_MISSING: "DRIVER MISSING"
            }
            
            # Add dashboard overlay BELOW driver monitor on LEFT side
            dashboard_width = driver_monitor_width
            dashboard_height = 180
            dashboard_x = 10
            dashboard_y = dm_y + driver_monitor_height + 10  # Position just below driver monitor with 10px gap
            
            # Create semi-transparent overlay
            overlay = frame.copy()
            cv2.rectangle(overlay, (dashboard_x, dashboard_y), 
                         (dashboard_x + dashboard_width, dashboard_y + dashboard_height), 
                         (50, 50, 50), -1)
            frame = cv2.addWeighted(frame, 0.6, overlay, 0.4, 0)
            
            # Add border to dashboard
            cv2.rectangle(frame, (dashboard_x, dashboard_y), 
                         (dashboard_x + dashboard_width, dashboard_y + dashboard_height), 
                         (200, 200, 200), 2)
            
            # Display info in dashboard
            text_x = dashboard_x + 10
            cv2.putText(frame, f'Driver State: {state_names[current_state]}', 
                       (text_x, dashboard_y + 35), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            cv2.putText(frame, f'Vehicle Speed: {int(current_speed)}%', 
                       (text_x, dashboard_y + 70), cv2.FONT_HERSHEY_SIMPLEX, 0.65, speed_color, 2)
            cv2.putText(frame, f'Speed: {int(current_speed_kmh)} km/h ({current_speed_kmh:.1f})', 
                       (text_x, dashboard_y + 105), cv2.FONT_HERSHEY_SIMPLEX, 0.6, speed_color, 2)
            cv2.putText(frame, f'Status: {speed_text}', 
                       (text_x, dashboard_y + 140), cv2.FONT_HERSHEY_SIMPLEX, 0.6, speed_color, 2)
            
            # Share combined frame with main thread for display
            with combined_frame_lock:
                combined_frame = frame.copy()
        
        # Don't show window here - will be shown in main thread
        # Sleep to control frame rate
        time.sleep(wait_time / 1000.0)
        
        # Check if system was stopped from other thread
        if not system_running:
            print("[INFO] Lane Detection - system shutdown signal received")
            break
    
    # Cleanup
    print("[INFO] Lane Detection - starting cleanup...")
    cap.release()
    # Don't destroy windows here - will be destroyed in main thread
    print("[INFO] Lane Detection Stopped")

# ==================== MAIN ====================
def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    global system_running
    print("\n[INFO] Ctrl+C detected - shutting down...")
    system_running = False
    cv2.destroyAllWindows()
    sys.exit(0)

def main():
    global system_running, combined_frame, combined_frame_lock
    
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    print("="*70)
    print("INTEGRATED DRIVER MONITORING SYSTEM")
    print("="*70)
    print()
    print("Single integrated window showing:")
    print("  • Lane Detection with driver monitoring overlay")
    print("  • Real-time drowsiness detection")
    print("  • Vehicle speed control based on driver state")
    print()
    print("Driver States:")
    print("  NORMAL       → Car drives at normal speed (100%)")
    print("  DROWSY       → Car slows down gradually")
    print("  DRIVER DOWN  → Car stops completely")
    print("  DRIVER MISSING → Car stops completely")
    print()
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║  HOW TO STOP THE SYSTEM:                                       ║")
    print("║  • Press 'Q' key in the window                                 ║")
    print("║  • Click on window first to make sure it's in focus            ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print("="*70)
    print()
    
    # Start both threads
    drowsy_thread = threading.Thread(target=drowsiness_detection_thread, daemon=False)
    lane_thread = threading.Thread(target=lane_detection_thread, daemon=False)
    
    drowsy_thread.start()
    time.sleep(1)  # Give camera time to initialize
    lane_thread.start()
    
    # Main thread handles GUI display (fixes Qt threading issues on Raspberry Pi)
    print("[INFO] Starting main display loop...")
    print("[INFO] Press Q or ESC to exit, or Ctrl+C in terminal")
    try:
        while system_running and (drowsy_thread.is_alive() or lane_thread.is_alive()):
            # Display the combined frame in main thread
            with combined_frame_lock:
                if combined_frame is not None:
                    cv2.imshow('Integrated Driver Monitoring System', combined_frame)
            
            # Handle keyboard input in main thread with shorter timeout
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q') or key == 27:  # Q or ESC
                print("[INFO] Exit key pressed - shutting down...")
                system_running = False
                break
            
            # Check if window was closed
            try:
                if cv2.getWindowProperty('Integrated Driver Monitoring System', cv2.WND_PROP_VISIBLE) < 1:
                    print("[INFO] Window closed - shutting down...")
                    system_running = False
                    break
            except:
                pass
            
            # If one thread stops, signal the other to stop
            if not drowsy_thread.is_alive() or not lane_thread.is_alive():
                if system_running:
                    print("[INFO] One thread stopped, stopping the other...")
                    system_running = False
                break
            
            # Small sleep to reduce CPU usage
            time.sleep(0.01)
                
    except KeyboardInterrupt:
        print("\n[INFO] Keyboard interrupt - shutting down...")
        system_running = False
    
    # Give threads a moment to see the shutdown signal
    time.sleep(0.5)
    
    # Wait for both threads to complete
    print("[INFO] Waiting for threads to complete cleanup...")
    drowsy_thread.join(timeout=3)
    lane_thread.join(timeout=3)
    
    # Force kill threads if they're still alive
    if drowsy_thread.is_alive():
        print("[WARN] Drowsiness thread did not exit cleanly")
    if lane_thread.is_alive():
        print("[WARN] Lane thread did not exit cleanly")
    
    # Force cleanup any remaining windows
    cv2.destroyAllWindows()
    time.sleep(0.2)  # Give time for windows to close
    
    print("\n" + "="*70)
    print("[SUCCESS] System shutdown complete")
    print("="*70)

if __name__ == "__main__":
    main()
