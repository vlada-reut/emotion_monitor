import math


class SimpleTracker:

    def __init__(self):

        self.objects = {}
        self.next_id = 0

    def update(self, detections):

        updated = {}

        for box in detections:

            x1, y1, x2, y2 = box

            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2

            found_id = None

            for obj_id, (px, py) in self.objects.items():

                dist = math.hypot(cx - px, cy - py)

                if dist < 50:
                    found_id = obj_id
                    break

            if found_id is None:

                found_id = self.next_id
                self.next_id += 1

            updated[found_id] = (cx, cy)

        self.objects = updated

        return updated