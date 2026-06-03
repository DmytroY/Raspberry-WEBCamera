import time
from flask import Flask, Response
from picamera2 import Picamera2
import cv2
import threading

app = Flask(__name__)
camera = Picamera2()

# reduce resolution to save resourses. Some variants:
# 4:3 Standard aspect ratio 320x240, 480 x 460, 640x480, 648x486, 1296x972, 2592x1944
# 16:9 wide 640x360, 1280x720, 2560x1440
# 1:1 square 720x720, 1944x1944
config = camera.create_video_configuration(main={"size": (1280, 720)})
# config["transform"] = libcamera.Transform(hflip=1, vflip=1)
camera.configure(config)

active_connections = 0
lock = threading.Lock()

def generate():
    last_frame_time = 0
    global active_connections
    with lock:
        active_connections += 1
        if active_connections == 1:
            camera.start() # at least 1 viewer connected - start camera
    try:
        while True:
            # limit  FPS to save rosourses
            current_time = time.time()
            if current_time - last_frame_time < 0.1:   #10 fps
                time.sleep(0.02)
                continue
            last_frame_time = current_time
            frame = camera.capture_array()

            # Camera captures in BRG - convert to RGB as standard for jpeg 
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # rotation with openCV. flexible but resource consuming
            # frame = cv2.rotate(frame, cv2.ROTATE_180)

	    # jpeg quality 70% for save resourses
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if not ret:
                continue
            yield (b'--frame\r\n'
                b'Content-Type: image/jpg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    finally:
        with lock:
            active_connections -= 1
            if active_connections == 0:
                camera.stop()

@app.route('/')
def index():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__== '__main__':
    app.run(host='0.0.0.0', port=5000)
