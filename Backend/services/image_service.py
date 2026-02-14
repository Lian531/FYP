'''
image_service.py - Handles face detection and skin tone detection.

When a user uploads a photo, this file does two things:
1. Checks if there is exactly one face in the photo
2. Looks at the forehead and cheeks to figure out the skin tone

The skin tone result is always one of: white, brown, or black.
'''

import os
import cv2
import numpy as np

# Try to load the MediaPipe face detector when the app starts.
# If the model file is missing, we fall back to the simpler OpenCV method.
_MODEL_PATH  = os.path.join(os.path.dirname(__file__), "..", "face_detector.tflite")
_mp_detector = None

if os.path.exists(_MODEL_PATH):
    try:
        from mediapipe.tasks.python import vision, BaseOptions
        _mp_detector = vision.FaceDetector.create_from_options(
            vision.FaceDetectorOptions(
                base_options=BaseOptions(model_asset_path=_MODEL_PATH),
                min_detection_confidence=0.4,
            )
        )
    except Exception as _e:
        print(f"[image_service] MediaPipe load failed: {_e}")
        _mp_detector = None

_USE_MEDIAPIPE = _mp_detector is not None

# Backup face detectors using OpenCV (used when MediaPipe is not available)
_cascade_frontal = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)
_cascade_alt = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_alt2.xml"
)
_cascade_profile = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_profileface.xml"
)

# If the image is too small, we scale it up before detecting faces
_MIN_DET_SIDE = 320


# Skin tone brightness cutoffs (based on the L value in LAB color space, range 0-255)
# These come from the average brightness of faces in our dataset:
#   white skin ≈ 181,  brown skin ≈ 154,  black skin ≈ 117
#
# Only change these two lines to recalibrate the classifier:
_WHITE_MIN = 165   # L >= 165 means white skin
_BROWN_MIN = 130   # L < 130 means black skin


# Error and warning messages shown to the user
_ERR_NO_FACE    = ("Face not detected. Please upload a clear photo of "
                   "a person's face.")
_ERR_MULTI_FACE = ("Multiple faces detected. Please upload a photo with "
                   "only one face.")
_WARN_LOW_CONF  = ("Skin tone confidence is low — lighting may be affecting "
                   "the result. For best accuracy, use natural light.")


def _upscale_for_detection(bgr: np.ndarray) -> tuple:
    '''
    Makes the image bigger if it is too small.
    Face detection works much better on larger images.
    Returns the resized image and scale values to map coordinates back to the original size.
    '''
    h, w  = bgr.shape[:2]
    short = min(h, w)
    if short >= _MIN_DET_SIDE:
        return bgr, 1.0, 1.0
    scale = _MIN_DET_SIDE / short
    up    = cv2.resize(bgr, (int(w * scale), int(h * scale)),
                       interpolation=cv2.INTER_LINEAR)
    return up, w / up.shape[1], h / up.shape[0]


def _detect_faces(bgr: np.ndarray) -> list:
    
    up, sx, sy = _upscale_for_detection(bgr)

    if _USE_MEDIAPIPE:
        import mediapipe as mp
        rgb    = cv2.cvtColor(up, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = _mp_detector.detect(mp_img)
        boxes  = [(d.bounding_box.origin_x, d.bounding_box.origin_y,
                   d.bounding_box.width,    d.bounding_box.height)
                  for d in result.detections]
    else:
        gray = cv2.cvtColor(up, cv2.COLOR_BGR2GRAY)
        cv2.equalizeHist(gray, gray)
        boxes = []
        # Try the main frontal detector first, then the alternative one
        for cascade in (_cascade_frontal, _cascade_alt):
            raw = cascade.detectMultiScale(
                gray, scaleFactor=1.05, minNeighbors=3, minSize=(30, 30)
            )
            if len(raw) > 0:
                boxes = list(map(tuple, raw))
                break
        # If still nothing found, try the side-face detector
        if not boxes:
            raw = _cascade_profile.detectMultiScale(
                gray, scaleFactor=1.05, minNeighbors=3, minSize=(30, 30)
            )
            if len(raw) > 0:
                boxes = list(map(tuple, raw))
        # Last attempt with relaxed settings
        if not boxes:
            raw = _cascade_frontal.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=1, minSize=(20, 20)
            )
            if len(raw) > 0:
                boxes = list(map(tuple, raw))

    # Scale the coordinates back to match the original image size
    return [(int(x * sx), int(y * sy), int(w * sx), int(h * sy))
            for x, y, w, h in boxes]


def _sample_region(crop: np.ndarray):
    '''
    Gets the skin color values from one small region of the face.
    It filters out non-skin pixels like eyebrows, shadows, and hair.
    Returns [brightness, color_a, color_b] as averages, or None if not enough pixels.
    '''
    if crop is None or min(crop.shape[:2]) < 8:
        return None

    lab   = cv2.cvtColor(crop, cv2.COLOR_BGR2LAB)
    ycrcb = cv2.cvtColor(crop, cv2.COLOR_BGR2YCrCb)

    # Color filter to pick up skin pixels across all skin tones
    skin_mask = cv2.inRange(
        ycrcb,
        np.array([0,  120,  70], np.uint8),
        np.array([255, 175, 137], np.uint8),
    )

    # Also remove pixels that are too dark (shadows, eyebrows, beard edges)
    l_chan    = lab[:, :, 0]
    light_ok  = (l_chan > 40).astype(np.uint8) * 255
    final_mask = cv2.bitwise_and(skin_mask, light_ok)

    l_px = l_chan[final_mask > 0].astype(np.float32)
    a_px = lab[:, :, 1][final_mask > 0].astype(np.float32)
    b_px = lab[:, :, 2][final_mask > 0].astype(np.float32)

    if len(l_px) < 20:
        # Not enough skin pixels — use all non-dark pixels as a fallback
        flat_l = l_chan.flatten().astype(np.float32)
        flat_a = lab[:, :, 1].flatten().astype(np.float32)
        flat_b = lab[:, :, 2].flatten().astype(np.float32)
        keep   = flat_l > 40
        if keep.sum() < 10:
            return None
        l_px, a_px, b_px = flat_l[keep], flat_a[keep], flat_b[keep]

    return np.array([
        float(np.median(l_px)),   # median brightness (more reliable than mean)
        float(np.mean(a_px)),
        float(np.mean(b_px)),
    ])


def _classify_tone(avg_L: float) -> tuple:
    '''
    Decides if the skin tone is white, brown, or black based on brightness.
    Also gives a confidence score between 0 and 1 to show how certain the result is.
    Thresholds are set at the top of this file (_WHITE_MIN, _BROWN_MIN).
    '''
    if avg_L >= _WHITE_MIN:
        dist  = avg_L - _WHITE_MIN
        conf  = min(1.0, dist / 25.0)
        return "white", round(conf, 3)

    if avg_L >= _BROWN_MIN:
        mid   = (_WHITE_MIN + _BROWN_MIN) / 2.0
        dist  = abs(avg_L - mid)
        conf  = min(1.0, dist / 15.0)
        return "brown", round(conf, 3)

    dist  = _BROWN_MIN - avg_L
    conf  = min(1.0, dist / 25.0)
    return "black", round(conf, 3)


def validate_face(image_path: str) -> tuple:
    '''
    Checks if the uploaded photo has exactly one face.
    Returns (True, None) if exactly one face is found.
    Returns (False, error message) if there are zero or more than one face.
    '''
    img = cv2.imread(image_path)
    if img is None:
        return False, ("The uploaded file is corrupted or not a valid image. "
                       "Please upload a clear photo.")

    faces = _detect_faces(img)

    if len(faces) == 0:
        return False, _ERR_NO_FACE

    if len(faces) > 1:
        return False, _ERR_MULTI_FACE

    return True, None


def detect_skin_tone(image_path: str) -> tuple:
    '''
    Detects the skin tone from a face photo.
    It finds the face, then checks three areas: forehead, left cheek, and right cheek.
    Returns the skin tone (white, brown, or black), a confidence score, and a warning if needed.
    '''
    img = cv2.imread(image_path)
    if img is None:
        return "brown", 0.0, _WARN_LOW_CONF

    faces = _detect_faces(img)

    if not faces:
        return "brown", 0.0, _ERR_NO_FACE

    # Use the one detected face (validate_face already rejected multi-face uploads)
    x, y, w, h = faces[0] if len(faces) == 1 \
                 else max(faces, key=lambda f: f[2] * f[3])

    # Make sure the face box stays within the image boundaries
    ih, iw = img.shape[:2]
    x = max(0, x);  y = max(0, y)
    w = min(w, iw - x);  h = min(h, ih - y)

    face = img[y: y + h, x: x + w]
    if face.size == 0:
        return "brown", 0.0, _WARN_LOW_CONF

    fh, fw = face.shape[:2]

    # Sample three skin areas within the face:
    #   forehead    — top part of the face, above the eyebrows
    #   left cheek  — lower left side, away from the nose
    #   right cheek — lower right side, away from the nose
    regions = [
        face[int(fh * 0.08): int(fh * 0.24), int(fw * 0.28): int(fw * 0.72)],  # forehead
        face[int(fh * 0.44): int(fh * 0.62), int(fw * 0.05): int(fw * 0.37)],  # left cheek
        face[int(fh * 0.44): int(fh * 0.62), int(fw * 0.63): int(fw * 0.95)],  # right cheek
    ]

    samples = [s for s in (_sample_region(r) for r in regions) if s is not None]

    if not samples:
        return "brown", 0.0, _WARN_LOW_CONF

    # Average the color values across all three regions
    avg = np.mean(samples, axis=0)
    avg_L = float(avg[0])

    tone, confidence = _classify_tone(avg_L)
    warning = _WARN_LOW_CONF if confidence < 0.25 else None
    return tone, confidence, warning
