import time
import os
import datetime
import threading
import cv2
import core.config as cfg

_cap        = None
_writer     = None
_rec_thread = None
_recording  = False


def is_recording():
    return _recording


def _capture_loop():
    global _writer
    segment_start = time.time()
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    while _recording:
        ret, frame = _cap.read()
        if not ret:
            continue
        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 65])
        with cfg.frame_lock:
            cfg.latest_frame = jpeg.tobytes()
        now = time.time()
        if _writer is None or (now - segment_start) >= cfg.SEGMENT_SEC:
            if _writer:
                _writer.release()
            date_str = datetime.datetime.now().strftime('%Y-%m-%d')
            video_dir = os.path.join(base, 'video', date_str)
            os.makedirs(video_dir, exist_ok=True)
            fname = os.path.join(video_dir, f"rec_{int(now)}.avi")
            h, w = frame.shape[:2]
            _writer = cv2.VideoWriter(fname, cv2.VideoWriter_fourcc(*'XVID'), 20, (w, h))
            segment_start = now
            print(f"錄影片段：{fname}")
        _writer.write(frame)
    if _writer:
        _writer.release()
    with cfg.frame_lock:
        cfg.latest_frame = b""


def start():
    global _cap, _recording, _rec_thread, _writer
    _cap = cv2.VideoCapture(0)
    _cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # 只保留最新 1 幀，避免舊幀堆積
    _writer = None
    _recording = True
    cfg.state["recording"] = True
    _rec_thread = threading.Thread(target=_capture_loop, daemon=True)
    _rec_thread.start()
    print("CAM ON / 錄影開始")


def stop():
    global _cap, _recording
    _recording = False
    cfg.state["recording"] = False
    if _rec_thread:
        _rec_thread.join(timeout=3)
    if _cap:
        _cap.release()
    _cap = None
    print("CAM OFF / 錄影停止")
