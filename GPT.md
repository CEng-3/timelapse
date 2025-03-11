# Secure SCP Transfer with Key Authentication

This guide outlines how to securely and efficiently transfer files between two Raspberry Pis (Pi B → Pi A) using SCP with SSH key authentication.

---

## **1. Set Up SSH Key Authentication**

### **On Pi B (Timelapse Generator):**
1. **Generate an SSH Key (if not already created):**
   ```bash
   ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
   ```
2. **Copy the Public Key to Pi A:**
   ```bash
   ssh-copy-id pi@192.168.64.121
   ```
3. **Test Passwordless Login:**
   ```bash
   ssh pi@192.168.64.121
   ```
   If successful, SSH will no longer prompt for a password.

---

## **2. Modify `timelapse.py` to Transfer the Video Automatically**

At the end of `timelapse.py`, add:

```python
import subprocess

PI_A_IP = "192.168.64.121"
REMOTE_DIR = "/home/raspberry/site/static/timelapse/piB/" # change directory structure on website

timelapse_filename = f"timelapse_{year}-{month}-{day}.mp4"
video_path = os.path.join(save_dir, timelapse_filename)

if os.path.exists(video_path):
    print("Transferring video to Pi A...")
    try:
        subprocess.run(["scp", video_path, f"pi@{PI_A_IP}:{REMOTE_DIR}"], check=True)
        print("Transfer complete.")
    except subprocess.CalledProcessError as e:
        print(f"Error during SCP transfer: {e}")
else:
    print("No video found to transfer.")
```

---

## **3. Verify the Transfer on Pi A**

After a timelapse is captured on Pi B, check if it arrived on Pi A:
```bash
ls -lh /home/raspberry/site/static/timelapse/piB/
```

---

## **Alternative: Use Rsync for More Efficient Transfers**

For large files, `rsync` can be more efficient than SCP:
```bash
rsync -avz -e ssh /home/raspberry/timelapse/wherever_the_video_is.mp4 pi@192.168.64.121:/home/raspberry/site/static/timelapse/piB/
```

---

## **Final Notes**
✅ **Secure:** Uses SSH encryption.
✅ **Automated:** No password prompts after initial setup.
✅ **Efficient:** Simple and fast file transfer.

Refer to this guide whenever setting up SCP-based file transfers between Raspberry Pis!