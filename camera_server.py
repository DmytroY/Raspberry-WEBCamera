from flask import Flask, Response
from picamera2 import Picamera2
import cv2

app = Flask(__name__)
camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"size": (640, 480)}))
camera.start()

def generate():
    while True:
        frame = camera.capture_array()
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        yield (b'--frame\r\n'
            b'Content-Type: image/jpg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/')
def index():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__== '__main__':
    app.run(host='0.0.0.0', port=5000)
