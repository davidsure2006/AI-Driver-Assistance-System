"""
Real-time Lane Detection Display

This script processes a video and displays the lane detection in a window in real-time.

Usage:
    python realtime_test.py [VIDEO_PATH]
    
    If no VIDEO_PATH is provided, it will use 'project_video.mp4' by default
"""

import numpy as np
import cv2
import sys
from CameraCalibration import CameraCalibration
from Thresholding import Thresholding
from PerspectiveTransformation import PerspectiveTransformation
from LaneLines import LaneLines

class RealtimeLaneDetection:
    """ Real-time lane detection with window display """
    
    def __init__(self):
        """ Initialize the lane detection pipeline """
        print("Initializing lane detection pipeline...")
        self.calibration = CameraCalibration('camera_cal', 9, 6)
        self.thresholding = Thresholding()
        self.transform = PerspectiveTransformation()
        self.lanelines = LaneLines()
        print("Pipeline initialized successfully!")

    def process_frame(self, img):
        """ Process a single frame """
        out_img = np.copy(img)
        img = self.calibration.undistort(img)
        img = self.transform.forward(img)
        img = self.thresholding.forward(img)
        img = self.lanelines.forward(img)
        img = self.transform.backward(img)

        out_img = cv2.addWeighted(out_img, 1, img, 0.6, 0)
        out_img = self.lanelines.plot(out_img)
        return out_img

    def process_video_realtime(self, video_path):
        """ Process video and display in real-time window """
        print(f"Opening video: {video_path}")
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print(f"Error: Could not open video file: {video_path}")
            return
        
        # Get video properties
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        print(f"Video properties:")
        print(f"  Resolution: {width}x{height}")
        print(f"  FPS: {fps}")
        print(f"  Total frames: {total_frames}")
        print("\nProcessing video...")
        print("Press 'q' to quit, 'p' to pause/resume, 's' to save current frame")
        
        frame_count = 0
        paused = False
        
        while True:
            if not paused:
                ret, frame = cap.read()
                
                if not ret:
                    print("\nEnd of video reached")
                    break
                
                frame_count += 1
                
                # Process the frame
                try:
                    processed_frame = self.process_frame(frame)
                    
                    # Add frame counter
                    cv2.putText(processed_frame, f"Frame: {frame_count}/{total_frames}", 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                    
                    # Display the frame
                    cv2.imshow('Lane Detection - Press Q to quit, P to pause, S to save', processed_frame)
                    
                    # Print progress every 50 frames
                    if frame_count % 50 == 0:
                        progress = (frame_count / total_frames) * 100
                        print(f"Progress: {frame_count}/{total_frames} frames ({progress:.1f}%)")
                    
                except Exception as e:
                    print(f"Error processing frame {frame_count}: {e}")
                    # Display original frame if processing fails
                    cv2.imshow('Lane Detection - Press Q to quit, P to pause, S to save', frame)
            
            # Handle key presses (wait time adjusted for smooth playback)
            key = cv2.waitKey(max(1, int(1000/fps))) & 0xFF
            
            if key == ord('q') or key == ord('Q'):
                print("\nQuitting...")
                break
            elif key == ord('p') or key == ord('P'):
                paused = not paused
                if paused:
                    print("Paused - Press 'p' to resume")
                else:
                    print("Resumed")
            elif key == ord('s') or key == ord('S'):
                filename = f"frame_{frame_count}.jpg"
                cv2.imwrite(filename, processed_frame)
                print(f"Saved current frame as {filename}")
        
        # Clean up
        cap.release()
        cv2.destroyAllWindows()
        print("Done!")

def main():
    # Get video path from command line argument or use default
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
    else:
        video_path = 'project_video.mp4'
    
    print("="*60)
    print("Real-time Lane Detection Display")
    print("="*60)
    
    # Create lane detection instance
    detector = RealtimeLaneDetection()
    
    # Process video with real-time display
    detector.process_video_realtime(video_path)

if __name__ == "__main__":
    main()
