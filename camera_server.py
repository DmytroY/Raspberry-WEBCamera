import time
from flask import Flask, Response
from picamera2 import Picamera2
import cv2

app = Flask(__name__)
camera = Picamera2()

# config = camera.create_video_configuration()

# reduce resolution to save resourses (320x240, 480 x 460, 640x480)
config = camera.create_video_configuration(main={"size": (320, 240)})

# flip with camera settings if needed. it's consumes less resourses
# compare to rotating by OpenCV later..
# config["transform"] = libcamera.Transform(hflip=1, vflip=1)
camera.configure(config)
camera.start()

def generate():
    last_frame_time = 0
    while True:
        # limit  FPS to save rosourses
        current_time = time.time()
        if current_time - last_frame_time < 0.067:   #15 fps
            time.sleep(0.01)
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

@app.route('/')
def index():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__== '__main__':
    app.run(host='0.0.0.0', port=5000)
