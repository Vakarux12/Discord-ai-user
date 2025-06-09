import json

def get_personality_for(user_id):
    try:
        with open("config/personality.json", "r") as f:
            base = json.load(f)
    except:
        base = {}

    try:
        with open("memory/personality_override.json", "r") as f:
            overrides = json.load(f)
    except:
        overrides = {}

    return {**base, **overrides.get(str(user_id), {})}

def set_override(user_id, field, value):
    try:
        with open("memory/personality_override.json", "r") as f:
            overrides = json.load(f)
    except:
        overrides = {}

    uid = str(user_id)
    if uid not in overrides:
        overrides[uid] = {}

    overrides[uid][field] = value

    with open("memory/personality_override.json", "w") as f:
        json.dump(overrides, f, indent=2)