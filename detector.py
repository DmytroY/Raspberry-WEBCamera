import time
from flask import Flask, Response, render_template_string
from picamera2 import Picamera2
import cv2
import threading
from queue import Queue, Empty
from collections import deque
from ultralytics import YOLO

app = Flask(__name__)
camera = Picamera2()

# config = camera.create_video_configuration(main={"size": (640, 640), "format": "RGB888"}) 
config = camera.create_video_configuration(main={"size": (960, 960), "format": "RGB888"}) 
camera.configure(config)

# model = YOLO("yolov5n.pt")
model = YOLO("yolov5nu_ncnn_model_960")
object_counts = {}

active_connections = 0
lock = threading.Lock()

# Thread communication variables
raw_frame_queue = Queue(maxsize=1)       # Passes raw frames to YOLO thread
encoded_frame_pool = {"bytes": None}     # Stores the latest processed JPEG
frame_ready = threading.Event()
camera_active = threading.Event()
client_queues = deque()

def camera_thread_func():
    """Background thread: Captures frames at a constant rate without waiting for YOLO"""
    while True:
        camera_active.wait()
        start_time = time.time()
        
        try:
            frame = camera.capture_array()

            # If the image has 4 channels (BGRA/XBGR), slice it to 3 channels (BGR)
            # if frame.shape[2] == 4:
            #     frame = frame[:, :, :3]
            
            # Non-blocking push to YOLO thread; drops frame if YOLO is still busy
            try:
                raw_frame_queue.put_nowait(frame)
            except:
                pass
                
        except Exception as e:
            print(f"Capture error: {e}")
            
        # Maintain ~0.33 FPS capture rate limit
        delay = 3 - (time.time() - start_time)
        if delay > 0:
            time.sleep(delay)

def yolo_worker_func():
    """Background thread: Processes the latest available frame from the queue"""
    global object_counts
    while True:
        frame = raw_frame_queue.get()  # Blocks until a new frame arrives
        try:

            # detection classes: 0 = person, 1 = bicycle, 2 = car, 3 = motorcycle, 16 = dog, 25 = umbrella. 
            # For save resourses swith augmentaton off and process only objects with confidention score > 
            results = model(frame, classes=[0, 25], imgsz=960, augment=True, conf=0.4)[0]
            
            for box in results.boxes:
                cls_id = int(box.cls[0])
                label = model.names[cls_id]
                with lock:
                    object_counts[label] = object_counts.get(label, 0) + 1
            
            annotated_frame = results.plot()
            ret, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            
            if ret:
                frame_bytes = buffer.tobytes()
                with lock:
                    encoded_frame_pool["bytes"] = frame_bytes
                frame_ready.set()
                
        except Exception as e:
            print(f"YOLO error: {e}")

def broadcast_thread_func():
    """Background thread: Distributes available processed frames to clients"""
    while True:
        frame_ready.wait()
        frame_ready.clear()
        
        with lock:
            frame_to_send = encoded_frame_pool["bytes"]
            queues_to_update = list(client_queues)
            
        for q in queues_to_update:
            try:
                q.put_nowait(frame_to_send)
            except:
                pass

def generate():
    """Generator for streaming frames to individual clients"""
    global active_connections, client_queues

    client_queue = Queue(maxsize=1)
    with lock:
        active_connections += 1
        client_queues.append(client_queue)
        if active_connections == 1:
            camera.start()
            camera_active.set()
    try:
        while True:
            try:
                frame_data = client_queue.get(timeout=1.0)
                if frame_data is None:
                    break
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
            except Empty:
                continue
    except (GeneratorExit, ConnectionResetError):
        pass
    finally:
        with lock:
            active_connections -= 1
            if client_queue in client_queues:
                client_queues.remove(client_queue)
            if active_connections == 0:
                camera_active.clear()
                # Flush raw queue to unblock worker if waiting
                try:
                    raw_frame_queue.get_nowait()
                except:
                    pass
                camera.stop()

@app.route('/')
def index():
    return render_template_string("""
        <html>
          <head><title>Pi Camera</title></head>
          <body>
            <h1>Camera Stream</h1>
            <img src="{{ url_for('video_feed') }}" width="960" height="960" />
          </body>
        </html>
    """)

@app.route('/video_feed')
def video_feed():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    # Initialize and run threads
    threading.Thread(target=camera_thread_func, daemon=True).start()
    threading.Thread(target=yolo_worker_func, daemon=True).start()
    threading.Thread(target=broadcast_thread_func, daemon=True).start()
    
    app.run(host='0.0.0.0', port=5000, threaded=True)