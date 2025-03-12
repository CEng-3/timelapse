from datetime import datetime, timedelta
import os, time, logging, subprocess
import glob
import math

# Configuration
send_video = True  # Flag to control remote transfer of completed video
remote_host = "192.168.64.121"
remote_user = "tower-garden"
remote_dir = "/home/tower-garden/site/static/cam2"

capture_duration = timedelta(minutes=1)
capture_interval = 10  # seconds between photos

image_width = 1280 # Max: 4608 / 2304 (HDR mode)
image_height = 720 # Max: 2592 / 1296 (HDR mode)

# Determine start time for purpose of creating directories
d = datetime.now()
year, month, day = f"{d.year:04d}", f"{d.month:02d}", f"{d.day:02d}"
hour, minute = f"{d.hour:02d}", f"{d.minute:02d}"

save_dir = f"timelapse_{year}-{month}-{day}"
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

# Set up a log file
log_filepath = os.path.join(save_dir, "log_file.log")
logging.basicConfig(filename=log_filepath, level=logging.DEBUG, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

# Define a specific format for recovery information
# This makes it easier to find and parse
def log_capture_state(image_number, start_time_iso, last_capture_time_iso):
    logging.info(f"CAPTURE_STATE: image_count={image_number}, start_time={start_time_iso}, last_capture_time={last_capture_time_iso}")

start_time = None
image_count = 1
last_capture_time = None
is_recovery = False

# Try to recover from previous run
if os.path.exists(log_filepath):
    try:
        with open(log_filepath, "r") as log_file:
            lines = log_file.readlines()
            # Look for the most recent CAPTURE_STATE entry
            for line in reversed(lines):
                if "CAPTURE_STATE:" in line:
                    parts = line.strip().split("CAPTURE_STATE: ")[1]
                    # Parse key=value pairs
                    state_parts = parts.split(", ")
                    recovery_data = {}
                    
                    for part in state_parts:
                        key_value = part.split("=", 1)
                        if len(key_value) == 2:
                            key, value = key_value
                            recovery_data[key] = value
                    
                    try:
                        if "image_count" in recovery_data:
                            # Important: increment the image count from the log
                            # so we don't overwrite the previous image
                            image_count = int(recovery_data["image_count"]) + 1
                            is_recovery = True
                        
                        if "start_time" in recovery_data:
                            start_time = datetime.fromisoformat(recovery_data["start_time"])
                        
                        if "last_capture_time" in recovery_data:
                            last_capture_time = datetime.fromisoformat(recovery_data["last_capture_time"])
                        
                        print(f"Recovered from log: image_count={image_count} (incremented), start_time={start_time}")
                        if last_capture_time:
                            print(f"Last capture was at: {last_capture_time}")
                    except ValueError as e:
                        logging.warning(f"Error parsing recovery data: {e}, resetting")
                        start_time = None
                        last_capture_time = None
                    
                    break
    except Exception as e:
        logging.error(f"Error reading log file: {e}")
        start_time = None
        last_capture_time = None

# Verify image count against existing files to avoid duplicates
if os.path.exists(save_dir):
    existing_images = sorted(glob.glob(os.path.join(save_dir, "*.jpg")))
    if existing_images:
        # Extract the highest image number from existing files
        highest_num = 0
        for img_path in existing_images:
            img_name = os.path.basename(img_path)
            try:
                num = int(os.path.splitext(img_name)[0])
                highest_num = max(highest_num, num)
            except ValueError:
                continue
        
        # Make sure our counter is higher than any existing image
        image_count = max(image_count, highest_num + 1)
        print(f"Highest image number found: {highest_num}, next image will be: {image_count}")

if start_time is None:
    # Start a new session
    start_time = datetime.now()
    last_capture_time = None
    print(f"Starting new session at {start_time}")
    logging.info(f"Starting new session at {start_time.isoformat()}")

# Calculate when the next photo should be taken based on the schedule
now = datetime.now()

# If we have a last capture time, calculate when the next one should be
if last_capture_time:
    # Calculate how many intervals have elapsed since the last capture
    time_since_last_capture = now - last_capture_time
    intervals_elapsed = time_since_last_capture.total_seconds() / capture_interval
    
    # If less than one interval has passed, wait for the remainder
    if intervals_elapsed < 1:
        wait_time = capture_interval - time_since_last_capture.total_seconds()
        print(f"Resuming: Waiting {wait_time:.1f} seconds to maintain schedule")
        time.sleep(wait_time)
    else:
        # If we're late by more than one interval
        intervals_to_skip = math.floor(intervals_elapsed)
        print(f"Resuming: {intervals_to_skip} intervals elapsed since last capture")
        print("Taking a photo immediately and then resuming schedule")

# Only log initial state if this is not a recovery
if not is_recovery:
    current_time = datetime.now()
    if last_capture_time is None:
        last_capture_time = current_time
    log_capture_state(image_count - 1, start_time.isoformat(), last_capture_time.isoformat())

# Main capture loop
while datetime.now() - start_time < capture_duration:
    current_time = datetime.now()
    elapsed_time = current_time - start_time
    print(f"Elapsed time: {elapsed_time}, capture duration: {capture_duration}")

    # Ensure 4-digit zero-padded filename for correct sorting
    image_name = f"{image_count:04d}.jpg"
    image_path = os.path.join(save_dir, image_name)

    # Capture image with error handling
    try:
        subprocess.run([
            "libcamera-still", "-o", image_path, "-t", "1000", "-n",
            "--width", str(image_width), "--height", str(image_height)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

        if os.path.exists(image_path):
            # Update the last capture time to now
            last_capture_time = datetime.now()
            logging.info(f"Captured image: {image_name}")
            # Update capture state after each successful capture
            log_capture_state(image_count, start_time.isoformat(), last_capture_time.isoformat())
        else:
            logging.warning(f"Image {image_path} missing after capture attempt!")
    except subprocess.CalledProcessError as e:
        logging.error(f"Camera error: {e}")
        time.sleep(60) # Wait before retrying
        continue

    image_count += 1
    print(f"Captured {image_name}, waiting {capture_interval} seconds...")
    time.sleep(capture_interval)

print("Image capture completed.")

# Rest of your code for video generation remains unchanged
video_path = os.path.join(save_dir, f"timelapse_{year}-{month}-{day}.mp4")

# Use sorted glob to ensure correct image order
image_files = sorted(glob.glob(os.path.join(save_dir, "*.jpg")))
num_images = len(image_files)
print(f"Total images captured: {num_images}")

# Verify we have multiple images
if num_images < 2:
    print("Not enough images to create timelapse. Exiting.")
    logging.error("Insufficient images to create timelapse")
    exit(1)

# Create timelapse using ffmpeg with explicit duration calculation
try:
    # Create timelapse using ffmpeg with more explicit settings
    ffmpeg_cmd = [
        "ffmpeg", 
        "-framerate", "1",  # 1 frame per second
        "-pattern_type", "glob", 
        "-i", os.path.join(save_dir, "*.jpg"),
        "-c:v", "libx264", 
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={image_width}:{image_height}",
        "-r", "1",  # output framerate
        "-g", "1",  # keyframe every frame
        "-shortest",  # ensure full length
        video_path
    ]
    
    print("Executing ffmpeg command:", " ".join(ffmpeg_cmd))
    
    # Run ffmpeg with detailed error logging
    result = subprocess.run(
        ffmpeg_cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE, 
        text=True, 
        check=False
    )
    
    # Log the detailed output
    logging.info(f"FFmpeg stdout: {result.stdout}")
    logging.error(f"FFmpeg stderr: {result.stderr}")
    
    # Print the output for immediate visibility
    print("FFmpeg stdout:", result.stdout)
    print("FFmpeg stderr:", result.stderr)
    
    # Raise an exception if the return code is non-zero
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, ffmpeg_cmd, result.stdout, result.stderr)

    # Verify video file exists and has some size
    if os.path.exists(video_path):
        video_size = os.path.getsize(video_path)
        print(f"Video created. Size: {video_size} bytes")
        
        # Optional: Get video duration using ffprobe
        try:
            duration_result = subprocess.run([
                "ffprobe", 
                "-v", "error", 
                "-show_entries", "format=duration", 
                "-of", "default=noprint_wrappers=1:nokey=1", 
                video_path
            ], capture_output=True, text=True)
            print(f"Video duration: {duration_result.stdout.strip()} seconds")
        except Exception as e:
            print(f"Could not get video duration: {e}")

except Exception as e:
    logging.error(f"Error creating timelapse: {e}")
    print(f"Error creating timelapse: {e}")

logging.debug(f" > Timelapse saved as {video_path}")
print(f"Timelapse created as {video_path}")

# Transfer the video file to the remote host if send_video is enabled and video exists
if send_video and os.path.exists(video_path):
    try:
        print(f"Transferring video to {remote_user}@{remote_host}:{remote_dir}...")
        logging.info(f"Starting transfer of {video_path} to {remote_user}@{remote_host}:{remote_dir}")
        
        # Get the filename part without the path
        video_filename = os.path.basename(video_path)
        
        # First ensure the remote directory exists
        print("Ensuring remote directory exists...")
        mkdir_cmd = [
            "ssh", 
            f"{remote_user}@{remote_host}", 
            f"mkdir -p {remote_dir}"
        ]
        
        mkdir_result = subprocess.run(
            mkdir_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        if mkdir_result.returncode != 0:
            print(f"Warning: Could not ensure remote directory exists: {mkdir_result.stderr}")
            logging.warning(f"Failed to ensure remote directory exists: {mkdir_result.stderr}")
        
        # Execute scp command to transfer the file
        transfer_cmd = [
            "scp",
            video_path,
            f"{remote_user}@{remote_host}:{remote_dir}/{video_filename}"
        ]
        
        print("Executing command:", " ".join(transfer_cmd))
        
        result = subprocess.run(
            transfer_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False  # Don't raise exception, handle manually
        )
        
        if result.returncode == 0:
            print(f"Video transfer completed successfully")
            logging.info(f"Video transfer completed successfully")
        else:
            print(f"Error transferring video. Return code: {result.returncode}")
            print(f"Error details: {result.stderr}")
            logging.error(f"Error transferring video. Return code: {result.returncode}")
            logging.error(f"Error details: {result.stderr}")
    except Exception as e:
        print(f"Unexpected error during transfer: {e}")
        logging.error(f"Unexpected error during transfer: {e}")
else:
    if not send_video:
        print("Video transfer skipped (send_video flag is disabled)")
    elif not os.path.exists(video_path):
        print("Video transfer skipped (video file not found)")