import json

def update_emotion(state):
    try:
        with open("memory/mood.json", "r") as f:
            mood = json.load(f)
    except:
        mood = {"current_mood": "neutral", "energy": 0.5, "emotions": []}

    mood["current_mood"] = state
    mood["emotions"].append(state)

    with open("memory/mood.json", "w") as f:
        json.dump(mood, f, indent=2)

def get_emotion_context():
    try:
        with open("memory/mood.json", "r") as f:
            mood = json.load(f)
        return f"her mood is currently {mood.get('current_mood', 'neutral')}"
    except:
        return "her mood is unclear"