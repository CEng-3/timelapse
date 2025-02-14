#
# TODO: Organise variable names

from datetime import datetime, timedelta
import os, time, logging, subprocess

capture_duration = timedelta(hours=12)
capture_interval = 600 # 10 minutes

image_width = 800 # Max: 4608 / 2304 (HDR mode)
image_height = 600 # Max: 2592 / 1296 (HDR mode)

# Determine start time for purpose of creating directories
d = datetime.now()
year, month, day = f"{d.year:04d}", f"{d.month:02d}", f"{d.day:02d}"
hour, minute = f"{d.hour:02d}", f"{d.minute:02d}"

save_dir = f"timelapse_{year}-{month}-{day}"
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

# Set up a log file
log_file = os.path.join(save_dir, "log_file.log")
logging.basicConfig(filename=log_file, level=logging.DEBUG)
logging.debug(f" /\/\ Timelapse Log - starting for {save_dir} /\/\ ")

start_time = None
image_count = 1

if os.path.exists(log_file):
    with open(log_file, "r") as log_file:
        lines = log_file.readlines()
        if lines:
            last_line = lines[-1].strip()
            parts = last_line.split()
            if len(parts) >= 3:
                image_count = int(parts[1]) + 1 # Resume from the last image + 1
                start_time = datetime.fromisoformat(parts[2]) # Recover start time

if start_time is None:
    start_time = datetime.now()

while datetime.now() - start_time < capture_duration:
    image_name = f"{image_count:04d}.jpg"
    image_path = os.path.join(save_dir, image_name)

    # Capture image with error handling
    try:
        subprocess.run(["libcamera-still", "-o", image_path, "--width", str(image_width), "--height", str(image_height), "--sharpness", "40", "--awb", "auto", "--metering", "average", "-v"], check=True)
        logging.info(f"{image_count} {datetime.now().isoformat()} - captured {image_path}")
    except subprocess.CalledProcessError as e:
        logging.error(f"Camera error: {e}")
        time.sleep(60) # Wait before retrying
        continue

    image_count += 1
    time.sleep(capture_interval)

print("Image capture completed.")

video_path = os.path.join(save_dir, f"timelapse_{year}-{month}-{day}.mp4")

# Create timelapse using ffmpeg
subprocess.run(["ffmpeg", "-framerate", "6", "-i", os.path.join(save_dir, "%04d.jpg"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "scale=1280:720", video_path], check=True)
logging.debug(f" > Timelapse saved as {video_path}")
print(f"Timelapse created as {video_path}")