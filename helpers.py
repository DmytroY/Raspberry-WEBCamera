import cv2

# --- Motion ROI settings ---
SCALE = 0.25               # diff is computed on a 1/4 size image
BLUR = 9                   # smaller kernel because the image is smaller
DIFF_THRESHOLD = 30
MARGIN = 60                # in full-resolution pixels
MIN_MOTION_PIXELS = 20     # ignore noise below this (in downscaled pixels)

def to_small_gray(frame):
    small = cv2.resize(frame, None, fx=SCALE, fy=SCALE, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(gray, (BLUR, BLUR), 0)

def find_motion_roi(prev_small, curr_small, frame_w, frame_h):
    """Returns (x0, y0, x1, y1) in full-frame coordinates, or None if no motion."""
    diff = cv2.absdiff(prev_small, curr_small)
    _, thresh = cv2.threshold(diff, DIFF_THRESHOLD, 255, cv2.THRESH_BINARY)

    if cv2.countNonZero(thresh) < MIN_MOTION_PIXELS:
        return None

    x, y, w, h = cv2.boundingRect(thresh)
    x0 = max(0, int(x / SCALE) - MARGIN)
    y0 = max(0, int(y / SCALE) - MARGIN)
    x1 = min(frame_w, int((x + w) / SCALE) + MARGIN)
    y1 = min(frame_h, int((y + h) / SCALE) + MARGIN)
    return x0, y0, x1, y1