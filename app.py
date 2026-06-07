import threading
from queue import Queue, Empty
from collections import deque
from flask import Flask, Response, render_template
from app_detector import VideoDetector

app = Flask(__name__)
detector = VideoDetector()

active_connections = 0
client_queues = deque()
lock = threading.Lock()

def broadcast_thread_func():
    while True:
        detector.frame_ready.wait()
        detector.frame_ready.clear()
        
        with detector.lock:
            frame_to_send = detector.encoded_frame_pool["bytes"]
        
        with lock:
            queues_to_update = list(client_queues)
            
        for q in queues_to_update:
            try:
                q.put_nowait(frame_to_send)
            except:
                pass

def generate():
    global active_connections, client_queues
    client_queue = Queue(maxsize=1)
    
    with lock:
        active_connections += 1
        client_queues.append(client_queue)
        if active_connections == 1:
            detector.start_camera()
            
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
                detector.stop_camera()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    threading.Thread(target=detector.camera_thread_func, daemon=True).start()
    threading.Thread(target=detector.yolo_worker_func, daemon=True).start()
    threading.Thread(target=broadcast_thread_func, daemon=True).start()
    
    app.run(host='0.0.0.0', port=5000, threaded=True)