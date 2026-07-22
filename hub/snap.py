"""Grab one still for ROI/scale setup.  Fixed focus + fixed exposure + fixed WB."""
from picamera2 import Picamera2
import time

cam = Picamera2()
cam.configure(cam.create_still_configuration(main={"size": (4608, 2592)}))
cam.set_controls({
    "AfMode": 0, "LensPosition": 1.82,   # Manual.  dioptre = 1 / distance(m)
    "AeEnable": False, "ExposureTime": 20000, "AnalogueGain": 2.0,
    "AwbEnable": False, "ColourGains": (1.8, 1.6),
})
cam.start()
time.sleep(2)
cam.capture_file("calib.jpg")
cam.stop()
print("saved calib.jpg")
