'''
compute_centroids.py - Calculates the average skin color for each skin tone class.

It reads all the training images from the Face Dataset folder and measures the
average LAB color values for Black, Brown, and White skin tones separately.

The results are saved to skin_centroids.npy and can be used as reference points
for the skin tone classifier.

Run from Backend/:
    python compute_centroids.py
'''

import os
import sys
import cv2
import numpy as np

_HERE    = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(_HERE, "Face Dataset")
OUT_PATH = os.path.join(_HERE, "skin_centroids.npy")

# The order here must match image_service.py: white=0, brown=1, black=2
CLASSES = [("White", 0), ("Brown", 1), ("Black", 2)]

_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def _detect_face(bgr):
    '''Finds the largest face in the image and returns its position, or None if not found.'''
    gray  = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    faces = _cascade.detectMultiScale(
        gray, scaleFactor=1.1, minNeighbors=3, minSize=(30, 30)
    )
    if len(faces) == 0:
        return None
    return max(faces, key=lambda f: f[2] * f[3])


def _sample_lab(bgr):
    '''
    Reads the skin color from the cheek and jaw area of a face image.
    Returns [brightness, color_a, color_b] as averages, or None if not enough pixels.
    '''
    h, w = bgr.shape[:2]

    # Focus on the lower half of the face (cheeks and jaw)
    r0    = int(h * 0.40)
    r1    = int(h * 0.80)
    strip = bgr[r0:r1, :]
    if strip.shape[0] < 8 or strip.shape[1] < 8:
        strip = bgr

    # Color filter to find skin pixels (widened to work for very dark skin tones too)
    ycrcb = cv2.cvtColor(strip, cv2.COLOR_BGR2YCrCb)
    mask  = cv2.inRange(
        ycrcb,
        np.array([0,   120,  70], np.uint8),
        np.array([255, 180, 135], np.uint8),
    )

    lab  = cv2.cvtColor(strip, cv2.COLOR_BGR2LAB)
    l_px = lab[:, :, 0][mask > 0].astype(float)
    a_px = lab[:, :, 1][mask > 0].astype(float)
    b_px = lab[:, :, 2][mask > 0].astype(float)

    if len(l_px) < 20:
        # Not enough skin pixels — use all non-dark pixels as backup
        flat_l = lab[:, :, 0].flatten().astype(float)
        flat_a = lab[:, :, 1].flatten().astype(float)
        flat_b = lab[:, :, 2].flatten().astype(float)
        keep   = flat_l > 20          # lower threshold to keep dark skin pixels
        if keep.sum() < 10:
            return None
        l_px, a_px, b_px = flat_l[keep], flat_a[keep], flat_b[keep]

    return np.array([np.median(l_px), np.mean(a_px), np.mean(b_px)],
                    dtype=np.float32)


def main():
    if not os.path.isdir(DATA_DIR):
        print(f"ERROR: dataset not found at {DATA_DIR}")
        sys.exit(1)

    # Store color samples for each class so we can average them later
    class_vectors = {0: [], 1: [], 2: []}

    for folder_name, cls_idx in CLASSES:
        cls_dir = os.path.join(DATA_DIR, folder_name)
        if not os.path.isdir(cls_dir):
            print(f"  WARNING: folder not found: {cls_dir}")
            continue

        img_files = [f for f in os.listdir(cls_dir)
                     if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        ok = 0

        for fname in img_files:
            bgr = cv2.imread(os.path.join(cls_dir, fname))
            if bgr is None:
                continue

            # Try to find a face — these images are already cropped so fallback is fine
            face_box = _detect_face(bgr)
            if face_box is not None:
                fx, fy, fw, fh = face_box
                face = bgr[fy: fy + fh, fx: fx + fw]
            else:
                face = bgr   # already a face chip

            vec = _sample_lab(face)
            if vec is not None:
                class_vectors[cls_idx].append(vec)
                ok += 1

        total = len(img_files)
        print(f"  {folder_name:6s}: {ok}/{total} images sampled successfully")

    # Average the color values for each class to get the centroid
    centroids = np.zeros((3, 3), dtype=np.float32)
    print("\nComputed centroids [L, a, b] in OpenCV-LAB:")
    label_names = {0: "white", 1: "brown", 2: "black"}
    for cls_idx in range(3):
        vecs = class_vectors[cls_idx]
        if not vecs:
            print(f"  {label_names[cls_idx]}: NO DATA -- using default centroid")
            centroids[cls_idx] = _DEFAULT[cls_idx]
        else:
            c = np.mean(vecs, axis=0)
            centroids[cls_idx] = c
            print(f"  {label_names[cls_idx]:6s}: L={c[0]:.1f}  a={c[1]:.1f}  b={c[2]:.1f}"
                  f"  (n={len(vecs)})")

    np.save(OUT_PATH, centroids)
    print(f"\nSaved -> {OUT_PATH}")
    print("Restart the Flask server to pick up the new centroids.")


# Default color values used if a skin tone folder is missing from the dataset
_DEFAULT = np.array([
    [175.0, 133.0, 148.0],   # white
    [128.0, 141.0, 151.0],   # brown
    [ 72.0, 143.0, 143.0],   # black
], dtype=np.float32)


if __name__ == "__main__":
    main()
