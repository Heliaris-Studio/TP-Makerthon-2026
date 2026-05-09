#!/usr/bin/env python3
"""
MJPEG Camera Streamer
  開啟瀏覽器前往 http://<Pi-IP>:8080 即可觀看即時畫面
"""

import cv2
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

CAMERA_INDEX = 0
HOST = "0.0.0.0"
PORT = 8080
JPEG_QUALITY = 60  # 0-100

cap = cv2.VideoCapture(CAMERA_INDEX)

if not cap.isOpened():
    raise RuntimeError(f"無法開啟攝影機 /dev/video{CAMERA_INDEX}，請確認裝置是否連接。")

cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

frame_lock = threading.Lock()
latest_frame: bytes = b""


def capture_loop():
    global latest_frame
    while True:
        ret, frame = cap.read()
        if not ret:
            continue
        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
        with frame_lock:
            latest_frame = jpeg.tobytes()


class StreamHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 關閉每次請求的 log 輸出

    def do_GET(self):
        if self.path == "/":
            self._serve_index()
        elif self.path == "/stream":
            self._serve_stream()
        else:
            self.send_error(404)

    def _serve_index(self):
        html = b"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Camera Stream</title>
  <style>
    body { background:#111; display:flex; justify-content:center;
           align-items:center; height:100vh; margin:0; }
    img  { border:2px solid #444; max-width:100%; }
  </style>
</head>
<body>
  <img src="/stream">
</body>
</html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(html)))
        self.end_headers()
        self.wfile.write(html)

    def _serve_stream(self):
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()
        try:
            while True:
                with frame_lock:
                    data = latest_frame
                if data:
                    self.wfile.write(
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + data +
                        b"\r\n"
                    )
        except (BrokenPipeError, ConnectionResetError):
            pass  # 客戶端斷線，正常結束


if __name__ == "__main__":
    t = threading.Thread(target=capture_loop, daemon=True)
    t.start()

    server = HTTPServer((HOST, PORT), StreamHandler)
    print(f"串流已啟動 → http://<Pi-IP>:{PORT}")
    print("按 Ctrl+C 停止\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止串流。")
    finally:
        cap.release()
