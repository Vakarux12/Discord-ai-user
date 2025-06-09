
import json

def resolve_user(name):
    try:
        with open("memory/user_tags.json", "r") as f:
            tags = json.load(f)
        for key, uid in tags.items():
            if key.lower() == name.lower():
                return uid
    except:
        return None

def tag_user(user_id, name):
    try:
        with open("memory/user_tags.json", "r") as f:
            tags = json.load(f)
    except:
        tags = {}

    tags[name.lower()] = str(user_id)

    with open("memory/user_tags.json", "w") as f:
        json.dump(tags, f, indent=2)
