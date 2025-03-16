from datetime import datetime, timedelta
import os, time, logging, subprocess, glob, math, requests

# Configuration
send_video = True  # Flag to control remote transfer of completed video
remote_host = "192.168.64.121"
remote_user = "tower-garden"
remote_dir = "/home/tower-garden/site/static/cam2"
config_url = "http://tustower.com/timelapse-config.json"

def fetch_config():
    try:
        response = requests.get(config_url)
        response.raise_for_status()
        config = response.json()
        capture_window_start_str = config.get("start_time", "07:00:00")
        capture_window_end_str = config.get("end_time", "19:00:00")
        images_per_hour = float(config.get("images_per_hour", 360))
        
        # Convert start and end times to datetime objects
        start_time = datetime.strptime(capture_window_start_str, "%H:%M:%S")
        end_time = datetime.strptime(capture_window_end_str, "%H:%M:%S")
        
        # Calculate the total duration in seconds
        if end_time < start_time:
            end_time += timedelta(days=1)  # Handle overnight capture
        total_duration_seconds = (end_time - start_time).total_seconds()
        
        # Calculate the total number of images to be captured
        total_images = images_per_hour * (total_duration_seconds / 3600)
        
        # Calculate the capture interval in seconds
        capture_interval = total_duration_seconds / total_images
        
        return capture_window_start_str, capture_window_end_str, capture_interval
    except Exception as e:
        logging.error(f"Error fetching config: {e}")
        return "07:00:00", "19:00:00", 3600 / 2  # default values

# Get initial configuration
capture_window_start_str, capture_window_end_str, capture_interval = fetch_config()

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
def log_capture_state(image_number, sequence_start_time_iso, last_capture_time_iso):
    logging.info(f"CAPTURE_STATE: image_count={image_number}, " + 
                 f"sequence_start_time={sequence_start_time_iso}, " + 
                 f"last_capture_time={last_capture_time_iso}")

# Initialize key timing variables
sequence_start_time = None  # When the whole capture sequence began (preserved during restarts)
last_capture_time = None    # When the most recent photo was taken
image_count = 1
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
                        
                        if "sequence_start_time" in recovery_data:
                            sequence_start_time = datetime.fromisoformat(recovery_data["sequence_start_time"])
                        
                        if "last_capture_time" in recovery_data:
                            last_capture_time = datetime.fromisoformat(recovery_data["last_capture_time"])
                        
                        print(f"Recovered from log: image_count={image_count} (incremented)")
                        print(f"Sequence started at: {sequence_start_time}")
                        if last_capture_time:
                            print(f"Last capture was at: {last_capture_time}")
                    except ValueError as e:
                        logging.warning(f"Error parsing recovery data: {e}, resetting")
                        sequence_start_time = None
                        last_capture_time = None
                    
                    break
    except Exception as e:
        logging.error(f"Error reading log file: {e}")
        sequence_start_time = None
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

# Initialize sequence_start_time if this is a new sequence
if sequence_start_time is None:
    # For a new sequence, we'll set sequence_start_time on the first actual capture
    print(f"Starting new capture sequence")
    logging.info(f"Starting new capture sequence")

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
if not is_recovery and sequence_start_time is not None:
    current_time = datetime.now()
    if last_capture_time is None:
        last_capture_time = current_time
    log_capture_state(image_count - 1, sequence_start_time.isoformat(), last_capture_time.isoformat())

# Main capture loop
while True:
    current_time = datetime.now()
    current_time_str = current_time.strftime("%H:%M:%S")
    
    if current_time_str >= capture_window_start_str and current_time_str <= capture_window_end_str:
        # If this is our first capture ever in this sequence, set the sequence start time
        if sequence_start_time is None:
            sequence_start_time = current_time
            print(f"Setting sequence start time to {sequence_start_time}")
            logging.info(f"Setting sequence start time to {sequence_start_time}")
        
        # Calculate elapsed time since first capture in the sequence
        elapsed_time = current_time - sequence_start_time
        print(f"Elapsed time in sequence: {elapsed_time}, capture interval: {capture_interval}")

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
                log_capture_state(image_count, sequence_start_time.isoformat(), last_capture_time.isoformat())
            else:
                logging.warning(f"Image {image_path} missing after capture attempt!")
        except subprocess.CalledProcessError as e:
            logging.error(f"Camera error: {e}")
            time.sleep(60) # Wait before retrying
            continue

        image_count += 1
        print(f"Captured {image_name}, waiting {capture_interval} seconds...")
        time.sleep(capture_interval)
        
        # Refresh config before next capture
        capture_window_start_str, capture_window_end_str, capture_interval = fetch_config()
        print("Fetching new config...")
        print(f"New capture window: {capture_window_start_str} - {capture_window_end_str}, " + 
              f"new capture interval: {capture_interval}")
    else:
        if current_time_str > capture_window_end_str:
            print(f"Current time {current_time_str} is past the end time {capture_window_end_str}. " + 
                  f"Taking final photo and exiting.")
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
                    logging.info(f"Captured final image: {image_name}")
                    # Update capture state after each successful capture
                    log_capture_state(image_count, sequence_start_time.isoformat(), last_capture_time.isoformat())
                else:
                    logging.warning(f"Image {image_path} missing after capture attempt!")
            except subprocess.CalledProcessError as e:
                logging.error(f"Camera error: {e}")
                time.sleep(60) # Wait before retrying
                continue

            image_count += 1
            break
        else:
            print(f"Current time {current_time_str} is outside the capture window " +
                  f"({capture_window_start_str} - {capture_window_end_str}). Waiting...")
            time.sleep(1)  # Check every second if within the capture window

print("Image capture completed.")