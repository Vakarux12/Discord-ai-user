
import json
import random

def load_mood():
    try:
        with open("memory/mood.json", "r") as f:
            return json.load(f)
    except:
        return {"current_mood": "neutral", "energy": 0.5, "emotions": []}

def change_mood(new_mood):
    mood = load_mood()
    mood["current_mood"] = new_mood
    with open("memory/mood.json", "w") as f:
        json.dump(mood, f, indent=2)
