import torch
from ultralytics import YOLO
from flask import Flask, Response, jsonify
from picamera2 import Picamera2
import cv2

app = Flask(__name__)
camera = Picamera2()
camera.configure(camera.create_video_configuration(main={"size": (640, 480)}))
camera.start()

# Load YOLOv5
# model = torch.hub.load('ultralytics/yolov5', 'yolov5s')  # small, fast model
model = YOLO("yolov5n.pt")

object_counts = {}

def generate():
    global object_counts
    while True:
        frame = camera.capture_array()
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        # frame = cv2.rotate(frame, cv2.ROTATE_180)
        
        # Run detection
        results = model(frame)
        detections = results.xyxy[0]  # Get detections
        
        # Count objects
        object_counts = {}
        for det in detections:
            label = results.names[int(det[5])]
            object_counts[label] = object_counts.get(label, 0) + 1
        
        # Draw bboxes
        frame = cv2.cvtColor(results.render()[0], cv2.COLOR_RGB2BGR)
        
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        if not ret:
            continue
        yield (b'--frame\r\n'
            b'Content-Type: image/jpg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/')
def index():
    return '''
    <html>
        <body>
            <h1>Raspberry Pi Camera</h1>
            <img src="/video_feed" width="640" height="480">
            <h2>Objects Detected:</h2>
            <p id="counts">Loading...</p>
            <script>
                setInterval(() => {
                    fetch('/counts').then(r => r.json()).then(data => {
                        document.getElementById('counts').innerHTML = JSON.stringify(data);
                    });
                }, 1000);
            </script>
        </body>
    </html>
    '''

@app.route('/video_feed')
def video_feed():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/counts')
def get_counts():
    return jsonify(object_counts)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
