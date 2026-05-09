#!/usr/bin/env python3
import time
import threading
import RPi.GPIO as GPIO
import cv2
from http.server import BaseHTTPRequestHandler, HTTPServer

TRIG = 17
ECHO = 27
LED_GREEN = 26
LED_RED   = 19
THRESHOLD = 25  # cm

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(TRIG, GPIO.OUT)
GPIO.setup(ECHO, GPIO.IN)
GPIO.setup(LED_GREEN, GPIO.OUT)
GPIO.setup(LED_RED,   GPIO.OUT)
GPIO.output(TRIG, GPIO.LOW)
time.sleep(0.5)

cap = None
latest_frame = b""
frame_lock = threading.Lock()
streaming = False

def capture_loop():
    global latest_frame
    while True:
        if not streaming or cap is None:
            time.sleep(0.05)
            continue
        ret, frame = cap.read()
        if ret:
            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            with frame_lock:
                latest_frame = jpeg.tobytes()

def measure():
    GPIO.output(TRIG, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(TRIG, GPIO.LOW)
    deadline = time.time() + 0.02
    while GPIO.input(ECHO) == GPIO.LOW:
        if time.time() > deadline:
            return None
    t0 = time.time()
    deadline = t0 + 0.02
    while GPIO.input(ECHO) == GPIO.HIGH:
        if time.time() > deadline:
            return None
    return (time.time() - t0) * 34300 / 2

class StreamHandler(BaseHTTPRequestHandler):
    def log_message(self, *args): pass

    def do_GET(self):
        if self.path == "/":
            html = b"<html><body style='background:#111'><img src='/stream'></body></html>"
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        elif self.path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
            try:
                while True:
                    with frame_lock:
                        data = latest_frame
                    if data:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_error(404)

server = HTTPServer(("0.0.0.0", 8080), StreamHandler)
threading.Thread(target=server.serve_forever, daemon=True).start()
threading.Thread(target=capture_loop, daemon=True).start()

print("啟動中... 串流位址 http://10.164.207.88:8080")
print(f"距離閾值：{THRESHOLD} cm  |  按 Ctrl+C 停止\n")

try:
    while True:
        dist = measure()
        if dist is None:
            print("量測逾時")
            time.sleep(0.5)
            continue

        if dist < THRESHOLD:
            if not streaming:
                cap = cv2.VideoCapture(0)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                streaming = True
                print(f"距離 {dist:.1f} cm < {THRESHOLD} cm → 紅燈 / 攝影機 ON")
            GPIO.output(LED_RED,   GPIO.HIGH)
            GPIO.output(LED_GREEN, GPIO.LOW)
        else:
            if streaming:
                streaming = False
                cap.release()
                cap = None
                with frame_lock:
                    latest_frame = b""
                print(f"距離 {dist:.1f} cm ≥ {THRESHOLD} cm → 綠燈 / 攝影機 OFF")
            GPIO.output(LED_RED,   GPIO.LOW)
            GPIO.output(LED_GREEN, GPIO.HIGH)

        time.sleep(0.5)

except KeyboardInterrupt:
    print("\n停止。")
finally:
    GPIO.output(LED_RED,   GPIO.LOW)
    GPIO.output(LED_GREEN, GPIO.LOW)
    GPIO.cleanup()
    if cap is not None:
        cap.release()
    server.shutdown()
