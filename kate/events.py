
import json
from datetime import datetime

def add_diary_entry(text):
    try:
        with open("memory/diary.json", "r") as f:
            diary = json.load(f)
    except:
        diary = {}

    today = datetime.now().strftime("%Y-%m-%d")
    if today not in diary:
        diary[today] = []

    diary[today].append({
        "time": datetime.now().isoformat(),
        "entry": text
    })

    with open("memory/diary.json", "w") as f:
        json.dump(diary, f, indent=2)

def change_mood(new_mood):
    try:
        with open("memory/mood.json", "r") as f:
            mood = json.load(f)
    except:
        mood = {"current_mood": "neutral", "energy": 0.5, "emotions": []}

    mood["current_mood"] = new_mood

    with open("memory/mood.json", "w") as f:
        json.dump(mood, f, indent=2)

def ghost_user(user_id):
    try:
        with open("memory/relationships.json", "r") as f:
            rel = json.load(f)
    except:
        rel = {}

    uid = str(user_id)
    if uid not in rel:
        rel[uid] = {}

    rel[uid]["ghosted"] = True

    with open("memory/relationships.json", "w") as f:
        json.dump(rel, f, indent=2)

def change_relationship(user_id, affection=0, trust=0):
    try:
        with open("memory/relationships.json", "r") as f:
            rel = json.load(f)
    except:
        rel = {}

    uid = str(user_id)
    if uid not in rel:
        rel[uid] = {"score": 0, "trust": 0}

    rel[uid]["score"] = rel[uid].get("score", 0) + affection
    rel[uid]["trust"] = rel[uid].get("trust", 0) + trust

    with open("memory/relationships.json", "w") as f:
        json.dump(rel, f, indent=2)

def set_role(user_id, role):
    try:
        with open("memory/relationships.json", "r") as f:
            rel = json.load(f)
    except:
        rel = {}

    uid = str(user_id)
    if uid not in rel:
        rel[uid] = {}

    rel[uid]["role"] = role

    with open("memory/relationships.json", "w") as f:
        json.dump(rel, f, indent=2)

def trigger_event(event_string, user_id=None):
    if event_string.startswith("add_diary:"):
        add_diary_entry(event_string[len("add_diary:"):].strip())
    elif event_string.startswith("change_mood:"):
        change_mood(event_string[len("change_mood:"):].strip())
    elif event_string.startswith("ghost:") and user_id:
        ghost_user(user_id)
    elif event_string.startswith("change_relationship:") and user_id:
        parts = event_string[len("change_relationship:"):].split(",")
        affection = int(parts[0]) if len(parts) > 0 else 0
        trust = int(parts[1]) if len(parts) > 1 else 0
        change_relationship(user_id, affection, trust)
    elif event_string.startswith("set_role:") and user_id:
        set_role(user_id, event_string[len("set_role:"):].strip())
