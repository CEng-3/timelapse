#
# TODO: Organise variable names

from datetime import datetime
import os, time, logging, subprocess

# Determine start time for purpose of creating directories
d = datetime.now()
year, month, day = f"{d.year:04d}", f"{d.month:02d}", f"{d.day:02d}"
hour, minute = f"{d.hour:02d}", f"{d.minute:02d}"

saveDir = f"timelapse_{year}-{month}-{day}_{hour}_{minute}"
if not os.path.exists(saveDir):
    os.makedirs(saveDir)

# Set up a log file
logging.basicConfig(filename=f"{saveDir}/.log_file", level=logging.DEBUG)
logging.debug(f" /\/\ Timelapse Log - starting for {saveDir} /\/\ ")

imageCount = 1
captureDuration = 10
captureInterval = 10 # Capture every 10 seconds
maxImages = (captureDuration * 60) // captureInterval

while imageCount < maxImages:
    d = datetime.now()
    textImageCount = f"{imageCount:04d}"

    # Determine current time for purpose of naming image files
    hour, minute = f"{d.hour:02d}", f"{d.minute:02d}"

    # Image size
    imgWidth = 800 # Max = 4608 / 2304 (HDR mode)
    imgHeight = 600 # Max = 2592 / 1296 (HDR mode)
    print(f"Image captured at {hour}:{minute} - saving...")

    imagePath = os.path.join(saveDir, f"{imageCount:04d}.jpg")

    # Capture image using libcamera
    subprocess.run(["libcamera-still", "-o", imagePath, "--width", str(imgWidth), "--height", str(imgHeight), "--sharpness", "40", "--awb", "auto", "--metering", "average", "-v"], check=True)
    logging.debug(f" > Image saved at {hour}:{minute} to directory {saveDir} as {imageCount}_{str(hour)}_{str(minute)}.jpg")

    imageCount += 1

    # Wait before next capture - currently 60 seconds
    time.sleep(captureInterval)

print("Image capture completed.")

video_path = os.path.join(saveDir, "video.mp4")

# Create timelapse using ffmpeg
subprocess.run(["ffmpeg", "-framerate", "10", "-i", os.path.join(saveDir, "%04d.jpg"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-vf", "scale=1280:720", video_path], check=True)
logging.debug(f" > Timelapse saved as {video_path}")