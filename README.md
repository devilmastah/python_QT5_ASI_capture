# # Python X-Ray Capture Module
# 
# Qt5-based Python application for live image acquisition, calibration, and snapshot capture
# using ZWO ASI cameras via the ASICamera2 SDK.
# 
# This repo is intended to be a reusable capture frontend and image processing module inside
# a larger X-ray imaging or CT imaging system. It provides:
# - a stable GUI application for camera preview and calibration
# - a snapshot capture pipeline that preserves image precision
# - an external control interface so other software can orchestrate the capture process
# 
# ---
# 
# ## High-level intent
# 
# The capture application is designed to be controlled in two ways:
# 
# 1. Manually via the GUI (operator adjusts exposure, gain, distortion, crop, calibration)
# 2. Programmatically via a local control server (ZeroMQ JSON RPC) from other processes
# 
# The intended orchestration pattern is:
# - A separate module controls the X-ray power supply and safety logic
# - That module requests the capture app to apply imaging settings
# - The power supply module enables the HV supply, waits for stability, triggers capture
# - The capture app returns the full path to the saved 16-bit TIFF snapshot
# 
# This keeps responsibilities separate:
# - capture app is responsible for camera data, calibration and saving images
# - PSU module is responsible for HV, timing, safety, sequencing and automation
# 
# ---
# 
# ## What this module does
# 
# ### Live preview
# - Captures frames continuously from the camera using a worker thread
# - Displays frames in the main Qt window
# - Applies lens distortion correction and optional crop to the preview stream
# - Keeps the internal pixel format as uint16 so full camera precision is preserved
# 
# ### Calibration (astrophotography style)
# - Supports capturing master calibration frames:
#   - Master Dark: median stack of N dark frames
#   - Master Flat: median stack of N flat frames, dark-corrected, then normalized to a float flat
# - Calibration is not applied to live preview by design, to keep UI responsive
# - Calibration is applied only during snapshot capture
# 
# ### Snapshot capture
# - Snapshot capture is the high-quality output path
# - Captures N frames (configurable)
# - Applies optional calibration per frame:
#   - dark subtraction (if enabled and available)
#   - flat correction by division (if enabled and available)
# - Stacks the calibrated frames (median)
# - Saves a final 16-bit TIFF image
# - Shows the final snapshot in a separate preview window
# 
# ---
# 
# ## Precision and data format
# 
# The ASI camera outputs 12-bit data. Internally the module uses uint16 everywhere.
# - Live frames are represented as uint16 numpy arrays
# - Saving uses 16-bit TIFF
# - Flat correction is stored as float32 TIFF because normalized flat values are fractional
# 
# This ensures no precision loss in later processing steps.
# 
# ---
# 
# ## Processing pipeline
# 
# ### Live preview pipeline
# 1. Capture frame from camera as uint16
# 2. Apply distortion correction (if enabled)
# 3. Apply crop (if enabled and not currently selecting a new crop)
# 4. Display frame
# 
# Note: dark/flat is NOT applied in preview.
# 
# ### Snapshot pipeline
# 1. Capture N frames from live stream (already distortion and crop corrected)
# 2. Load master dark and master flat if enabled
# 3. For each frame:
#    - Convert to float32
#    - If dark enabled: frame = frame - dark
#    - If flat enabled: frame = frame / flat_norm
#    - Clip to 0..65535 and convert back to uint16
# 4. Stack frames using median to reduce noise and reject outliers
# 5. Save stacked output to snapshots/snapshot_YYYYMMDD_HHMMSS.tiff
# 6. Show preview window with final frame
# 7. Return full file path (for external orchestration)
# 
# ---
# 
# ## Calibration logic details
# 
# ### Master Dark
# - Captured with the same exposure and gain as the intended snapshot capture
# - Captures N frames (default 10)
# - Combines via median to reject random noise and outliers
# - Saves as uint16 TIFF:
#   calibration/master_dark.tiff
# 
# ### Master Flat
# - Requires a master dark to exist first (project rule)
# - Captures N frames (default 10) of a uniform illumination field
# - Stacks via median into a flat image
# - Dark corrects the flat: flat_corr = flat - dark
# - Normalizes to a multiplicative flat:
#   flat_norm = flat_corr / mean(flat_corr)
# - Saves as float32 TIFF:
#   calibration/master_flat.tiff
# 
# The stored normalized flat is applied during snapshot capture by division.
# 
# ---
# 
# ## External control server
# 
# The application includes a server module intended for local inter-process control.
# Transport: ZeroMQ
# Pattern: REQ/REP
# Payload: JSON
# Default bind: tcp://127.0.0.1:5555
# 
# The server is intended for trusted, local automation scripts and modules.
# It is not designed as an internet-facing service.
# 
# ---
# 
# ## Server API
# 
# All requests are JSON objects:
# 
# {
#   "cmd": "<command_name>",
#   "args": { ... }
# }
# 
# All responses are JSON:
# 
# Success:
# {
#   "ok": true,
#   "result": { ... }
# }
# 
# Failure:
# {
#   "ok": false,
#   "error": "error message"
# }
# 
# ### Commands
# 
# #### 1) set_exposure_ms
# Sets exposure time in milliseconds.
# 
# Request:
# {
#   "cmd": "set_exposure_ms",
#   "args": { "value": 1200 }
# }
# 
# Behavior:
# - clamps value to the UI range (50..5000 ms)
# - updates the exposure slider, which triggers the camera update through the worker
# 
# Response:
# {
#   "ok": true,
#   "result": { "exposure_ms": 1200 }
# }
# 
# #### 2) set_gain
# Sets camera gain.
# 
# Request:
# {
#   "cmd": "set_gain",
#   "args": { "value": 80 }
# }
# 
# Behavior:
# - clamps to (0..600) by default
# - updates gain slider, which triggers worker update
# 
# Response:
# {
#   "ok": true,
#   "result": { "gain": 80 }
# }
# 
# #### 3) set_stack_n
# Sets how many frames are captured for snapshot stacking.
# 
# Request:
# {
#   "cmd": "set_stack_n",
#   "args": { "value": 15 }
# }
# 
# Behavior:
# - clamps to slider range (1..50)
# - updates stack slider and settings.json
# 
# Response:
# {
#   "ok": true,
#   "result": { "stack_n": 15 }
# }
# 
# #### 4) take_snapshot
# Captures a snapshot using the current stack_n and calibration settings.
# Returns the full file path of the saved TIFF.
# 
# Request:
# {
#   "cmd": "take_snapshot",
#   "args": {}
# }
# 
# Behavior:
# - captures N frames using the current preview pipeline output
# - applies calibration per frame if enabled
# - stacks and saves
# 
# Response:
# {
#   "ok": true,
#   "result": { "path": "D:\\...\\snapshots\\snapshot_20260123_120012.tiff" }
# }
# 
# Failure response example:
# {
#   "ok": false,
#   "error": "snapshot failed"
# }
# 
# #### 5) get_state
# Returns current state, useful for debugging or orchestration checks.
# 
# Request:
# {
#   "cmd": "get_state",
#   "args": {}
# }
# 
# Response:
# {
#   "ok": true,
#   "result": {
#     "exposure_us": 1200000,
#     "gain": 80,
#     "stack_n": 15,
#     "dark_enabled": true,
#     "flat_enabled": false
#   }
# }
# 
# ---
# 
# ## Typical orchestration flow (PSU module)
# 
# The expected control flow from an external module is:
# 
# 1. Configure camera:
#    set_exposure_ms
#    set_gain
#    set_stack_n
# 
# 2. Enable HV power supply and wait for stable operation
# 
# 3. Trigger capture:
#    take_snapshot
# 
# 4. Receive output file path and store it with metadata (power settings, timestamp)
# 
# 5. Disable HV power supply
# 
# The capture module does not control HV directly. That is a deliberate separation.
# 
# ---
# 
# ## Settings persistence
# 
# settings.json is stored in the working directory and updated automatically when UI
# controls change. It includes:
# - exposure_us
# - gain
# - distortion_manual settings
# - crop rect and enabled flag
# - dark frame path and enabled flag
# - flat frame path and enabled flag
# - snapshot stack_n
# 
# This allows the app to restore the previous configuration on startup.
# 
# ---
# 
# ## Directory output
# 
# calibration/
# - master_dark.tiff        (uint16)
# - master_flat.tiff        (float32)
# 
# snapshots/
# - snapshot_YYYYMMDD_HHMMSS.tiff  (uint16)
# 
# ---
# 
# ## Project structure
# 
# src/
# ├── main.py                    Main Qt application and UI wiring
# ├── capture_worker.py          Camera acquisition thread using ASICamera2
# ├── snapshot.py                Snapshot, stacking, calibration load and apply, preview window
# ├── server.py                  ZeroMQ RPC server implementation
# ├── server_bridge.py           Qt-safe bridge connecting server requests to UI actions
# ├── distortion.py              Manual lens distortion correction (cached remap)
# ├── crop.py                    Crop application logic
# ├── calibration_frames.py      Dark/flat creation and save helpers
# ├── image_display.py           16-bit display conversion helpers for Qt
# ├── settings_manager.py        Settings load/save helper
# ├── ui_distortion_crop_dialog.py  Distortion and crop UI dialog
# └── video_label.py             Clickable label for crop selection
# 
# server_control_example.py      Example remote control client (ZeroMQ)
# requirements.txt               Python dependencies
# settings.json                  Generated at runtime
# 
# ---
# 
# ## Setup
# 
# 1. Install ZWO ASICamera2 SDK from:
#    https://www.zwoastro.com/software/
# 
# 2. Make sure ASICamera2 native libs are available to the OS:
#    Windows: put DLL folder on PATH or in project folder
#    Linux: export LD_LIBRARY_PATH to include SDK library folder
# 
# 3. Create and activate venv:
#    python -m venv venv
#    venv\Scripts\activate
# 
# 4. Install Python dependencies:
#    pip install -r requirements.txt
# 
# 5. Run:
#    python src/main.py
# 
# ---
# 
# ## requirements.txt
# 
# numpy
# opencv-python
# PyQt5
# pyzmq
# zwoasi
# 
# ---
# 
# ## Sanity check
# 
# python -c "import zwoasi; print(zwoasi.get_num_cameras())"
# 
# ---
# 
# ## Notes and limitations
# 
# - The server is designed for trusted local usage
# - Long exposures mean capture functions can block for the exposure duration times stack count
# - Snapshot stacking currently uses median (robust and simple)
# - Calibration frame creation uses median stacking
# - Calibration is applied only to snapshot, not preview
# 
# ---
# 
# ## Future extensions (planned)
# 
# - Status publishing via ZeroMQ PUB (exposure, fps, last snapshot path, errors)
# - Add explicit commands:
#   - capture_dark
#   - capture_flat
#   - set_use_dark
#   - set_use_flat
# - Add metadata export (JSON next to TIFF)
# - Add snapshot naming or session folders for CT acquisition
# - Add timing hooks for PSU sequencing (but kept outside capture module)
# 
# ---


 ---
 
 ## Setup
 
 1. Install the ZWO ASICamera2 SDK from:
    https://www.zwoastro.com/software/
 
 2. Ensure the ASICamera2 native library is discoverable by the OS
    (PATH on Windows, LD_LIBRARY_PATH on Linux).
 
 3. Create a virtual environment:
 ```
    python -m venv venv
 ```
 4. Activate the virtual environment:
 ```
    Windows:
    venv\Scripts\activate
 
    Linux / macOS:
    source venv/bin/activate
 ```
 5. Install Python dependencies:
 ```
    pip install -r requirements.txt
 ```
 6. Run the application:
 ```
    python src/main.py
 ```
 ---
 
 ## requirements.txt
 ```
 numpy
 opencv-python
 PyQt5
 pyzmq
 zwoasi
 ```
 ---
 
 ## Sanity check
 
 To verify that the ASI SDK is correctly installed:
 ```
 python -c "import zwoasi; print(zwoasi.get_num_cameras())"
 ```
 You should see a number greater than 0 if a camera is connected.
 
 ---
