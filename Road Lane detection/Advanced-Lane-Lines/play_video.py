"""
Simple video player for lane detection output videos

Usage:
    python play_video.py [VIDEO_PATH]
    
    If no VIDEO_PATH is provided, it will use the output video from project_video
"""

import cv2
import sys
import os

def play_video(video_path):
    """Play a video file in a window"""
    
    # Check if file exists
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        return
    
    print("="*60)
    print("Lane Detection Video Player")
    print("="*60)
    print(f"\nPlaying: {video_path}")
    
    # Open video file
    cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        print(f"Error: Could not open video file: {video_path}")
        return
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    print(f"\nVideo properties:")
    print(f"  Resolution: {width}x{height}")
    print(f"  FPS: {fps}")
    print(f"  Total frames: {total_frames}")
    print(f"  Duration: {total_frames/fps:.2f} seconds")
    print("\nControls:")
    print("  'Q' or ESC - Quit")
    print("  'P' or SPACE - Pause/Resume")
    print("  'R' - Restart from beginning")
    print("  'S' - Save current frame as image")
    print("\nPress any key to start...")
    
    # Create window
    window_name = 'Lane Detection Simulation - Press Q to quit, P to pause'
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    frame_count = 0
    paused = False
    saved_count = 0
    
    while True:
        if not paused:
            ret, frame = cap.read()
            
            if not ret:
                print("\n\nEnd of video reached!")
                print("Press 'R' to restart or 'Q' to quit")
                paused = True
                continue
            
            frame_count += 1
            
            # Add frame counter and progress bar
            progress = (frame_count / total_frames) * 100
            time_current = frame_count / fps
            time_total = total_frames / fps
            
            # Add info overlay
            info_text = f"Frame: {frame_count}/{total_frames} | Time: {time_current:.1f}s/{time_total:.1f}s | Progress: {progress:.1f}%"
            cv2.putText(frame, info_text, (10, height - 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            
            # Show frame
            cv2.imshow(window_name, frame)
            
            # Print progress every 5%
            if frame_count % (total_frames // 20) == 0:
                print(f"Progress: {progress:.1f}% - Frame {frame_count}/{total_frames}")
        
        # Wait for key press (adjusted for smooth playback)
        wait_time = max(1, int(1000/fps)) if not paused else 0
        key = cv2.waitKey(wait_time) & 0xFF
        
        # Handle key presses
        if key == ord('q') or key == ord('Q') or key == 27:  # 27 is ESC
            print("\n\nQuitting...")
            break
        elif key == ord('p') or key == ord('P') or key == 32:  # 32 is SPACE
            paused = not paused
            if paused:
                print("\n⏸ Paused - Press 'P' or SPACE to resume")
            else:
                print("▶ Resumed")
        elif key == ord('r') or key == ord('R'):
            print("\n↻ Restarting video...")
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            frame_count = 0
            paused = False
        elif key == ord('s') or key == ord('S'):
            saved_count += 1
            filename = f"screenshot_{saved_count}_{frame_count}.jpg"
            cv2.imwrite(filename, frame)
            print(f"\n📸 Saved frame {frame_count} as '{filename}'")
    
    # Clean up
    cap.release()
    cv2.destroyAllWindows()
    print("\n✓ Done!")

def main():
    # Default video path
    default_video = r"output_videos\project_video_output.mp4"
    
    # Get video path from command line or use default
    if len(sys.argv) > 1:
        video_path = sys.argv[1]
    else:
        video_path = default_video
    
    play_video(video_path)

if __name__ == "__main__":
    main()
