'''
download_face_model.py - Downloads the face detection model file.

Only needs to be run once. It downloads the MediaPipe face detector
and saves it as face_detector.tflite in the Backend folder.
The app will use it automatically after restarting.

Run from Backend/:
    python download_face_model.py
'''

import os
import sys
import urllib.request

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_detector/blaze_face_short_range/float16/1/"
    "blaze_face_short_range.tflite"
)
OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_detector.tflite")


def main():
    if os.path.exists(OUT_PATH):
        print(f"Model already present at {OUT_PATH}")
        return

    print("Downloading face detector model from MediaPipe ...")
    try:
        urllib.request.urlretrieve(MODEL_URL, OUT_PATH)
        size_kb = os.path.getsize(OUT_PATH) // 1024
        print(f"Saved {size_kb} KB -> {OUT_PATH}")
        print("Restart Flask and the app will use MediaPipe for face detection automatically.")
    except Exception as e:
        print(f"Download failed: {e}")
        if os.path.exists(OUT_PATH):
            os.remove(OUT_PATH)
        sys.exit(1)


if __name__ == "__main__":
    main()
