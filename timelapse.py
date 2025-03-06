from datetime import datetime, timedelta
import os, time, logging, subprocess
import glob

capture_duration = timedelta(minutes=1)
capture_interval = 10

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
def log_capture_state(image_number, start_time_iso):
    logging.info(f"CAPTURE_STATE: image_count={image_number}, start_time={start_time_iso}")

start_time = None
image_count = 1

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
                    for part in state_parts:
                        if part.startswith("image_count="):
                            image_count = int(part.split("=")[1])
                        elif part.startswith("start_time="):
                            try:
                                start_time_str = part.split("=")[1]
                                start_time = datetime.fromisoformat(start_time_str)
                                print(f"Recovered start_time from log: {start_time}")
                                print(f"Recovered image_count from log: {image_count}")
                            except ValueError:
                                logging.warning("Invalid start time in log, resetting to current time.")
                                start_time = None
                    break
    except Exception as e:
        logging.error(f"Error reading log file: {e}")
        start_time = None

if start_time is None:
    start_time = datetime.now()
    print(f"Starting new session at {start_time}")
    logging.info(f"Starting new session at {start_time.isoformat()}")

# Log initial state
log_capture_state(image_count, start_time.isoformat())

while datetime.now() - start_time < capture_duration:
    elapsed_time = datetime.now() - start_time # Just for debugging
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
            logging.info(f"Captured image: {image_name}")
            # Update capture state after each successful capture
            log_capture_state(image_count, start_time.isoformat())
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