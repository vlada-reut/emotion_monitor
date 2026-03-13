from ultralytics import YOLO

class FaceDetector:

    def __init__(self):

        self.model = YOLO("face_yolov8n.pt")

    def detect(self, frame):

        results = self.model(frame, conf=0.4, imgsz=320, verbose=False)

        boxes = []

        for r in results:

            if r.boxes is None:
                continue

            for box in r.boxes.xyxy:

                x1,y1,x2,y2 = map(int,box)

                boxes.append((x1,y1,x2,y2))

        return boxes