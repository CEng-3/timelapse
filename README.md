# The Timelapse Script

## Setup

Make sure that the camera is connected to the Raspberry Pi and verify it by **opening a Terminal window and entering the `rpicam-hello` command**. If you connected the camera after turning on the Raspberry Pi, it most likely needs to be restarted for the camera to start working.

1. Update the Raspberry Pi and install Git
```
sudo apt update && sudo apt upgrade -y && sudo apt install git -y
```
2. Change directory to the home directory and clone the GitHub repository
```
cd
git clone https://github.com/CEng-3/timelapse.git
```
3. After Git has cloned the repository, change into the directory
```
cd timelapse
```
4. Run the script - no dependencies are required, so there's no need to create a virtual environment
```
python3 timelapse.py
```
