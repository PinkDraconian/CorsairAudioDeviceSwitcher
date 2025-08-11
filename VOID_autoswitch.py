# void_autoswitch.py
# Switch default playback device when CORSAIR VOID v2 links/unlinks.
# Requirements: pip install pywinusb ; SoundVolumeView.exe available.
# Tip: find your exact device names with: SoundVolumeView.exe /scomma out.csv

import time, threading, subprocess, os, sys
import pywinusb.hid as hid

# ---- CONFIG ----
VID, PID = 0x1B1C, 0x2A08
SOUNDVOLUMEVIEW = os.path.join(os.path.dirname(__file__), "SoundVolumeView.exe")
HEADSET_DEVICE_NAME = "2- CORSAIR VOID WIRELESS v2 Gaming Headset"
SPEAKERS_DEVICE_NAME = "Realtek(R) Audio"

# Behavior
ONLINE_AFTER = 25           # heartbeats required to consider online
# 50 was too much, when I walked to the fridge, it was already offline.
OFFLINE_GRACE = 6.0         # seconds without any data -> offline
CHECK_INTERVAL = 0.1        # seconds

# ---- STATE ----
last_rx = 0.0
hb_count = 0
online = False
lock = threading.Lock()
devices = []

def set_default_playback(name: str):
  if not os.path.isfile(SOUNDVOLUMEVIEW):
    print(f"[ERR] SoundVolumeView.exe not found at: {SOUNDVOLUMEVIEW}", flush=True)
    return
  try:
    # 1 = Default, 2 = Default communications
    subprocess.run([SOUNDVolumeVIEW := SOUNDVOLUMEVIEW, "/SetDefault", name, "1"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([SOUNDVolumeVIEW, "/SetDefault", name, "2"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"[OK] Default playback set to: {name}", flush=True)
  except subprocess.CalledProcessError as e:
    print(f"[ERR] Failed to set default device to '{name}': {e}", flush=True)

def on_data(data):
  """pywinusb gives a list[int]. data[0] is Report ID."""
  global last_rx, hb_count, online
  if not data or len(data) < 1:
    return
  now = time.time()
  with lock:
    last_rx = now
    print(data)
    if data[0] == 0x01:  # heartbeat stream we observed
      if hb_count < ONLINE_AFTER:
        hb_count += 1
      if not online and hb_count >= ONLINE_AFTER:
        online = True
        print(f"{now:.3f} ONLINE")
        set_default_playback(HEADSET_DEVICE_NAME)

def watcher():
  global last_rx, hb_count, online
  while True:
    time.sleep(CHECK_INTERVAL)
    now = time.time()
    with lock:
      if online and (now - last_rx) > OFFLINE_GRACE:
        online = False
        hb_count = 0
        print(f"{now:.3f} OFFLINE")
        set_default_playback(SPEAKERS_DEVICE_NAME)

def open_devices():
  flt = hid.HidDeviceFilter(vendor_id=VID, product_id=PID)
  devs = flt.get_devices()
  for d in devs:
    try:
      d.open()
      # One handler per device. pywinusb will invoke it for any input report.
      d.set_raw_data_handler(on_data)
      devices.append(d)
      print(f"[OK] Listening on: {d.device_path}")
    except Exception as e:
      print(f"[WARN] open failed: {e}")

def main():
  open_devices()
  if not devices:
    print("VOID receiver not found. Plug it in and run again.", file=sys.stderr)
    sys.exit(1)

  print("Listening for headset link/unlink. Ctrl+C to exit.")
  t = threading.Thread(target=watcher, daemon=True)
  t.start()

  try:
    while True:
      time.sleep(1)
  except KeyboardInterrupt:
    pass
  finally:
    for d in devices:
      try: d.close()
      except: pass

if __name__ == "__main__":
  main()