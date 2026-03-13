import cv2
from PySide6.QtCore import QThread, Signal

from core.face_detector import FaceDetector
from core.tracker import SimpleTracker
from services.emotion_stub import predict_emotion


class VideoWorker(QThread):

    frame_ready = Signal(object, object, object)

    def __init__(self):

        super().__init__()

        self.capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)

        self.detector = FaceDetector()
        self.tracker = SimpleTracker()

        self.active_faces = {}
        self.session_faces = {}

        self.running = True

    def run(self):

        while self.running:

            ret, frame = self.capture.read()

            if not ret:
                continue

            boxes = self.detector.detect(frame)

            tracked = self.tracker.update(boxes)

            current_ids = set()

            for obj_id,(cx,cy) in tracked.items():

                x1,y1,x2,y2 = boxes[list(tracked.keys()).index(obj_id)]

                face = frame[y1:y2,x1:x2]

                emotion = predict_emotion(face)

                self.active_faces[obj_id] = emotion
                self.session_faces[obj_id] = emotion

                current_ids.add(obj_id)

                cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0),2)

                cv2.putText(
                    frame,
                    f"{emotion}",
                    (x1,y1-10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0,255,0),
                    2
                )

            for fid in list(self.active_faces.keys()):
                if fid not in current_ids:
                    del self.active_faces[fid]

            self.frame_ready.emit(frame,self.active_faces,self.session_faces)

    def stop(self):

        self.running = False
        self.capture.release()