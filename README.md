 # Python X-Ray Capture Module
 
 Qt5-based Python application for live image acquisition, calibration, and
 snapshot capture using ZWO ASI cameras via the ASICamera2 SDK.
 
 This project is designed as a reusable capture frontend for X-ray imaging
 systems, with a strong focus on modularity and external control.
 
 ---
 
 ## What this module does
 
 - Displays a live camera feed from an ASI camera
 - Preserves full sensor precision (12-bit sensor stored as 16-bit)
 - Provides camera controls (exposure, gain)
 - Applies live lens distortion correction
 - Supports interactive crop selection (post-distortion)
 - Supports astrophotography-style calibration:
   - Dark frames
   - Flat frames (dark-corrected and normalized)
 - Captures snapshots with configurable frame stacking
 - Applies calibration only during snapshot capture (not live preview)
 - Saves final images as 16-bit TIFF files
 - Shows snapshot results in a separate preview window
 
 ---
 
 ## External control (server module)
 
 This application exposes a ZeroMQ-based control server that allows other
 software modules to control it programmatically.
 
 Supported remote commands:
 - Set exposure (ms)
 - Set gain
 - Set snapshot stack size
 - Trigger snapshot capture
 - Query current state
 
 This makes it suitable for integration with:
 - External power supply controllers
 - Automation scripts
 - CT scan orchestration software
 - Safety and interlock systems
 
 Communication is done using simple JSON request/response messages over ZeroMQ.
 
 ---
 
 ## Project structure
 ```
 src/
 ├── main.py                    # Main Qt application
 ├── capture_worker.py          # Camera acquisition thread (ASICamera2)
 ├── snapshot.py                # Snapshot, stacking, dark/flat logic
 ├── server.py                  # ZeroMQ RPC server
 ├── server_bridge.py           # Qt-safe bridge between server and UI
 ├── distortion.py              # Manual lens distortion correction
 ├── crop.py                    # Crop handling (post-distortion)
 ├── calibration_frames.py      # Dark/flat creation helpers
 ├── image_display.py           # 16-bit image display helpers
 ├── settings_manager.py        # JSON settings persistence
 ├── ui_distortion_crop_dialog.py
 └── video_label.py             # Clickable QLabel for crop selection
 
 server_control_example.py      # Example external control client
 requirements.txt               # Python dependencies
 settings.json                  # Runtime-generated settings file
 ```


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
 
 ## Notes
 
 - Live preview is optimized for responsiveness and does NOT apply
   dark/flat correction to avoid performance penalties.
 - All calibration is applied only during snapshot capture.
 - All images are processed and saved as 16-bit grayscale TIFFs.
 - The ZeroMQ server is intended for trusted internal use.
 
 ---
 
 ## Intended use
 
 This module is intended to be used as a stable building block inside a larger
 X-ray or CT imaging system, not as a monolithic application.
 
 It is safe to control it entirely headless via the server interface if needed.
 
 ---
