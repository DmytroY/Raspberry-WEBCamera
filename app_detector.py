import time
import cv2
import threading
from queue import Queue
from picamera2 import Picamera2
from ultralytics import YOLO

class VideoDetector:
    def __init__(self):
        self.camera = Picamera2()
        self.config = self.camera.create_video_configuration(main={"size": (960, 960), "format": "RGB888"})
        self.camera.configure(self.config)
        
        self.model = YOLO("yolov5nu_ncnn_model_960")
        self.object_counts = {}
        self.lock = threading.Lock()
        
        self.raw_frame_queue = Queue(maxsize=1)
        self.encoded_frame_pool = {"bytes": None}
        self.frame_ready = threading.Event()
        self.camera_active = threading.Event()

    def start_camera(self):
        self.camera.start()
        self.camera_active.set()

    def stop_camera(self):
        self.camera_active.clear()
        try:
            self.raw_frame_queue.get_nowait()
        except:
            pass
        self.camera.stop()

    def camera_thread_func(self):
        while True:
            self.camera_active.wait()
            start_time = time.time()
            try:
                frame = self.camera.capture_array()
                if frame.shape[2] == 4:
                    frame = frame[:, :, :3]
                try:
                    self.raw_frame_queue.put_nowait(frame)
                except:
                    pass
            except Exception as e:
                print(f"Capture error: {e}")
                
            delay = 3 - (time.time() - start_time)
            if delay > 0:
                time.sleep(delay)

    def yolo_worker_func(self):
        while True:
            frame = self.raw_frame_queue.get()
            try:
                results = self.model(frame, classes=[0, 25], imgsz=960, augment=True, conf=0.4)[0]
                
                for box in results.boxes:
                    cls_id = int(box.cls[0])
                    label = self.model.names[cls_id]
                    with self.lock:
                        self.object_counts[label] = self.object_counts.get(label, 0) + 1
                
                annotated_frame = results.plot()
                ret, buffer = cv2.imencode('.jpg', annotated_frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
                
                if ret:
                    with self.lock:
                        self.encoded_frame_pool["bytes"] = buffer.tobytes()
                    self.frame_ready.set()
            except Exception as e:
                print(f"YOLO error: {e}")