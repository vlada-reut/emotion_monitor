import random

EMOTIONS = [
    "happy",
    "neutral",
    "sad",
    "surprise",
    "angry"
]

def predict_emotion(face):

    return random.choice(EMOTIONS)