# void_autoswitch.py
# Switch default playback device when CORSAIR VOID v2 links/unlinks.
# Requirements: pip install pywinusb ; SoundVolumeView.exe available.

import time, threading, subprocess, os, sys
import pywinusb.hid as hid

# ---- CONFIG ----
VID, PID = 0x1B1C, 0x2A08
SOUNDVOLUMEVIEW = os.path.join(os.path.dirname(__file__), "SoundVolumeView.exe")
HEADSET_DEVICE_NAME = "CORSAIR VOID WIRELESS v2 Gaming Headset"
SPEAKERS_DEVICE_NAME = "Realtek(R) Audio"

CHECK_INTERVAL = 0.1         # seconds
DEBOUNCE_APPLY = 0.5         # min seconds between switch attempts

# ---- STATE ----
lock = threading.Lock()
devices = []

last_rx = 0.0
last_online_hb = 0.0
last_offline_hb = 0.0
last_apply = 0.0

state = "UNKNOWN"
desired = "UNKNOWN"

def set_default_playback(name: str):
  global last_apply
  if not os.path.isfile(SOUNDVOLUMEVIEW):
    print(f"[ERR] SoundVolumeView.exe not found at: {SOUNDVOLUMEVIEW}", flush=True)
    return
  now = time.time()
  if (now - last_apply) < DEBOUNCE_APPLY:
    return
  try:
    subprocess.run([SOUNDVOLUMEVIEW, "/SetDefault", name, "1"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run([SOUNDVOLUMEVIEW, "/SetDefault", name, "2"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    last_apply = now
    print(f"[OK] Default playback set to: {name}", flush=True)
  except subprocess.CalledProcessError as e:
    print(f"[ERR] Failed to set default device to '{name}': {e}", flush=True)

def apply_state(new_state: str, reason: str):
  global state
  if new_state == state:
    return
  state = new_state
  ts = time.time()
  print(f"{ts:.3f} STATE -> {state} ({reason})", flush=True)
  if state == "ONLINE":
    set_default_playback(HEADSET_DEVICE_NAME)
  elif state == "OFFLINE":
    set_default_playback(SPEAKERS_DEVICE_NAME)

def classify(data):
  if not data:
    return "OTHER"
  rid = data[0]
  if rid == 0x01:
    if len(data) >= 3:
      if data[1] == 1 and data[2] == 6:
        return "HB_ONLINE"
      if data[1] == 0 and data[2] == 18:
        return "HB_OFFLINE"
    return "HB_UNKNOWN"
  if rid == 0x03:
    if len(data) >= 6 and data[1] == 0 and data[2] == 1 and data[3] == 54 and data[4] == 0:
      if data[5] == 2:
        return "POWER_ON"
      if data[5] == 0:
        return "POWER_OFF"
    return "POWER_OTHER"
  return "OTHER"

def on_data(data):
  global last_rx, last_online_hb, last_offline_hb, desired
  now = time.time()
  evt = classify(data)
  with lock:
    last_rx = now

    if evt == "POWER_ON":
      desired = "ONLINE"
      apply_state("ONLINE", "power-on event")
      return
    if evt == "POWER_OFF":
      desired = "OFFLINE"
      apply_state("OFFLINE", "power-off event")
      return

    if evt == "HB_ONLINE":
      last_online_hb = now
      if desired != "ONLINE":
        desired = "ONLINE"
      if state != "ONLINE":
        apply_state("ONLINE", "online heartbeat")
      return

    if evt == "HB_OFFLINE":
      last_offline_hb = now
      if desired != "OFFLINE":
        desired = "OFFLINE"
      if state != "OFFLINE":
        apply_state("OFFLINE", "offline heartbeat")
      return

def watcher():
  while True:
    time.sleep(CHECK_INTERVAL)
    with lock:
      # Heartbeat reconciliation only
      if desired != state:
        if desired == "ONLINE" and last_online_hb > 0:
          apply_state("ONLINE", "reconcile to desired online")
        elif desired == "OFFLINE" and last_offline_hb > 0:
          apply_state("OFFLINE", "reconcile to desired offline")

def open_devices():
  flt = hid.HidDeviceFilter(vendor_id=VID, product_id=PID)
  devs = flt.get_devices()
  for d in devs:
    try:
      d.open()
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


###############
# Data format #
###############

# Offline heartbeat
# [1, 0, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

# Online heartbeat
# [1, 1, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

# Headset power off
# [3, 0, 1, 54, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
# Headset power on
# [3, 0, 1, 54, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
