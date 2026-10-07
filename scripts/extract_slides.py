#!/usr/bin/env python3
"""
Fast Slide & Keyframe Extractor with Progress Bar
"""
import sys
import time
from pathlib import Path
import cv2
import numpy as np
from slide_cropper import auto_crop_slide_content

def extract_slides(video_path: Path, output_dir: Path, step_secs: float = 6.0, diff_threshold: float = 12.0, progress_callback=None):
    output_dir.mkdir(parents=True, exist_ok=True)
    
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"Error opening video: {video_path}")
        return []

    try:
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        duration_secs = total_frames / fps
        step_frames = max(1, int(fps * step_secs))
    
        if not progress_callback:
            print(f"Starting slide scan: {duration_secs/60:.1f} mins ({total_frames} frames @ {fps:.1f} fps)", flush=True)
    
        saved_slides = []
        last_gray = None
        frame_idx = 0
        start_time = time.time()
        
        # Progress tracking
        last_print = 0
    
        while True:
            ret = cap.grab()
            if not ret:
                break
    
            if frame_idx % step_frames == 0:
                ret, frame = cap.retrieve()
                if not ret:
                    break
                
                # Progress bar update
                pct = (frame_idx / total_frames) * 100 if total_frames > 0 else 0
                mins_done = (frame_idx / fps) / 60
                mins_tot = duration_secs / 60

                if progress_callback:
                    progress_callback(pct, mins_done, mins_tot, len(saved_slides))
                elif time.time() - last_print > 1.5 or frame_idx == 0:
                    bar_len = 25
                    filled = int(bar_len * pct / 100)
                    bar = "█" * filled + "░" * (bar_len - filled)
                    print(f"[{bar}] {pct:5.1f}% | {mins_done:.1f}/{mins_tot:.1f} min | Found {len(saved_slides)} slides", flush=True)
                    last_print = time.time()
    
                # Resize thumbnail for fast comparison
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                small = cv2.resize(gray, (160, 90))
    
                is_new_slide = False
                if last_gray is None:
                    is_new_slide = True
                else:
                    diff = cv2.absdiff(small, last_gray)
                    score = np.mean(diff)
                    if score >= diff_threshold:
                        is_new_slide = True
    
                if is_new_slide:
                    sec = int(frame_idx / fps)
                    m = sec // 60
                    s = sec % 60
                    slide_name = f"slide_{m:02d}_{s:02d}.webp"
                    slide_path = output_dir / slide_name
                    
                    # Auto-crop meeting chrome / sidebars
                    cropped_frame = auto_crop_slide_content(frame)
                    
                    # Save compressed WebP (quality 75)
                    cv2.imwrite(str(slide_path), cropped_frame, [cv2.IMWRITE_WEBP_QUALITY, 75])
                    saved_slides.append({
                        "time": f"{m:02d}:{s:02d}",
                        "path": slide_path,
                        "name": slide_name
                    })
                    last_gray = small
    
            frame_idx += 1

    finally:
        cap.release()
    total_time = time.time() - start_time
    print(f"\n[█████████████████████████] 100.0% Complete! Extracted {len(saved_slides)} unique slides in {total_time:.1f}s.", flush=True)
    return saved_slides

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python extract_slides.py <path_to_video> [output_dir]")
        sys.exit(1)
    v_path = Path(sys.argv[1])
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else v_path.parent / "slides"
    extract_slides(v_path, out_dir)
