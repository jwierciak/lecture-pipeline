import cv2
import numpy as np

def auto_crop_slide_content(frame, min_area_ratio: float = 0.20, pad: int = 4):
    """
    Detects and crops the main presentation/document area from a lecture screen recording
    (e.g., PowerPoint, OneNote, Word, PDF in MS Teams/Zoom/Meet).
    Removes sidebars, attendee galleries, and dark window chrome.
    If no distinct content area is found, returns the original frame.
    """
    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # 1. Look for light/white document or slide background (threshold > 215)
    _, thresh = cv2.threshold(gray, 215, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best_rect = None
    max_area = 0

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        area = cw * ch
        # Must occupy a significant portion of screen and not be full screen border
        if area > (w * h * min_area_ratio):
            # Exclude full-width border or full-screen window itself
            if cw > (w * 0.98) and ch > (h * 0.98):
                continue
            if area > max_area:
                max_area = area
                best_rect = (x, y, cw, ch)

    if best_rect:
        x, y, cw, ch = best_rect
        # Add a tiny padding if possible
        x0 = max(0, x - pad)
        y0 = max(0, y - pad)
        x1 = min(w, x + cw + pad)
        y1 = min(h, y + ch + pad)
        return frame[y0:y1, x0:x1]

    # Return original if no clear slide box was detected
    return frame
