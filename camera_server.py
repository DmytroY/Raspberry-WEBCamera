import time
from flask import Flask, Response
from picamera2 import Picamera2
import cv2
import threading
from queue import Queue, Empty
from collections import deque


app = Flask(__name__)
camera = Picamera2()

config = camera.create_video_configuration(main={"size": (1280, 720)}) 
# config["transform"] = libcamera.Transform(hflip=1, vflip=1)
camera.configure(config)

active_connections = 0
lock = threading.Lock()
current_frame = None
frame_ready = threading.Event()
client_queues = deque()


def camera_thread_func():
    """Background thread that captures frames once and broadcasts to all clients"""
    global current_frame
    last_frame_time = 0


    while True:
        current_time = time.time()
        if current_time - last_frame_time < 0.12:   #8 fps
            time.sleep(0.02)
            continue
            
        last_frame_time = current_time

        try:
            frame = camera.capture_array()
            # camera format is BRG, to RGB convertion needed
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
            if ret:
                with lock:
                    current_frame = buffer.tobytes()
                    frame_ready.set()
        except Exception as e:
            print(f"Error capturing frame: {e}")
            time.sleep(0.1)

def generate():
    """Generator for streaming frames to individual clients"""
    global active_connections, client_queues

    # register the client
    client_queue = Queue(maxsize=1)
    with lock:
        active_connections += 1
        client_queues.append(client_queue)
        if active_connections == 1:
            camera.start()
    try:
        while True:
            try:
                # Wait for frame with timeout to allow graceful shutdown
                frame_data = client_queue.get(timeout=2)
                if frame_data is None:  # Shutdown signal
                    break

                yield (b'--frame\r\n'
                    b'Content-Type: image/jpg\r\n\r\n' + frame_data + b'\r\n')
            except Empty:
                continue
            except GeneratorExit:
                break
            except Exception as e:
                print(f"Error in generate: {e}")
                break           
    finally:
        # Unregister this client
        with lock:
            active_connections -= 1
            try:
                client_queues.remove(client_queue)
            except(ValueError, KeyError):
                pass
            if active_connections == 0:
                camera.stop()  # Stop camera when last client disconnects

def broadcast_frame_func():
    """Broadcast current frame to all connected clients"""
    global current_frame, client_queues

    while True:
        frame_ready.wait()  # Wait for new frame
        frame_ready.clear()

        with lock:
            frame_to_send = current_frame
            queues_to_update = list(client_queues)

        # Send to all clients (non-blocking, drop old frames if queue full)
        for q in queues_to_update:
            try:
                q.put_nowait(frame_to_send)
            except:
                pass  # Queue full, skip this client


@app.route('/')
def index():
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__== '__main__':
    # Start background threads
    camera_capture_thread = threading.Thread(target=camera_thread_func, daemon=True)
    camera_capture_thread.start()
    broadcast_thread = threading.Thread(target=broadcast_frame_func, daemon=True)
    broadcast_thread.start()
    app.run(host='0.0.0.0', port=5000, threaded=True)
