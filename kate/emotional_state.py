import json
import os
import math
import random
import re
from datetime import datetime, timedelta

# File path for storing Kate's emotional state
EMOTIONS_FILE = "memory/emotions.json"

# Base emotional parameters
DEFAULT_EMOTIONAL_STATE = {
    "mood": 50,           # 0-100: very negative to very positive
    "energy": 50,         # 0-100: exhausted to energetic
    "expressiveness": 50, # 0-100: reserved to expressive
    "last_updated": None, # ISO timestamp of last update
    "active_emotions": {} # Current active emotions with intensity
}

def ensure_emotions_file():
    """Create emotions file if it doesn't exist."""
    if not os.path.exists("memory"):
        os.makedirs("memory")
        
    if not os.path.exists(EMOTIONS_FILE):
        with open(EMOTIONS_FILE, "w") as f:
            json.dump(DEFAULT_EMOTIONAL_STATE, f, indent=2)

def get_emotional_state():
    """Get current emotional state, applying time-based decay."""
    ensure_emotions_file()
    
    try:
        with open(EMOTIONS_FILE, "r") as f:
            state = json.load(f)
            
        # Apply time-based decay if state is old
        if state.get("last_updated"):
            last_updated = datetime.fromisoformat(state["last_updated"])
            hours_since_update = (datetime.now() - last_updated).total_seconds() / 3600
            
            if hours_since_update > 1:
                # Apply decay toward baseline (50) for basic parameters
                decay_factor = min(1, hours_since_update / 24)  # Full decay takes 24 hours
                
                for param in ["mood", "energy", "expressiveness"]:
                    distance_from_baseline = state[param] - 50
                    state[param] = 50 + distance_from_baseline * (1 - decay_factor)
                
                # Decay active emotions
                expired_emotions = []
                for emotion, data in state["active_emotions"].items():
                    intensity = data["intensity"] * (1 - decay_factor * 2)  # Emotions decay faster
                    
                    if intensity < 10:  # Remove emotions below threshold
                        expired_emotions.append(emotion)
                    else:
                        state["active_emotions"][emotion]["intensity"] = intensity
                
                # Remove expired emotions
                for emotion in expired_emotions:
                    del state["active_emotions"][emotion]
                
                # Save the updated state with decay applied
                state["last_updated"] = datetime.now().isoformat()
                with open(EMOTIONS_FILE, "w") as f:
                    json.dump(state, f, indent=2)
        
        return state
    except Exception as e:
        print(f"Error getting emotional state: {e}")
        return DEFAULT_EMOTIONAL_STATE.copy()

def update_emotional_state(mood_change=0, energy_change=0, 
                          expressiveness_change=0, emotion=None, emotion_intensity=0):
    """
    Update Kate's emotional state based on various factors.
    """
    try:
        state = get_emotional_state()
        
        # Apply changes to base emotional parameters
        state["mood"] = max(0, min(100, state["mood"] + mood_change))
        state["energy"] = max(0, min(100, state["energy"] + energy_change))
        state["expressiveness"] = max(0, min(100, state["expressiveness"] + expressiveness_change))
        
        # Update timestamp
        current_time = datetime.now()
        state["last_updated"] = current_time.isoformat()
        
        # Add/update specific emotion if provided
        if emotion and emotion_intensity > 0:
            if emotion in state["active_emotions"]:
                # Blend existing and new intensity
                current = state["active_emotions"][emotion]["intensity"]
                new_intensity = max(current, emotion_intensity)  # Take higher intensity
                state["active_emotions"][emotion] = {
                    "intensity": new_intensity,
                    "timestamp": current_time.isoformat()
                }
            else:
                state["active_emotions"][emotion] = {
                    "intensity": emotion_intensity,
                    "timestamp": current_time.isoformat()
                }
        
        # Save updated state
        with open(EMOTIONS_FILE, "w") as f:
            json.dump(state, f, indent=2)
            
        return state
    except Exception as e:
        print(f"Error updating emotional state: {e}")
        return get_emotional_state()

def get_emotional_tone_modifiers():
    """
    Get text modifiers based on current emotional state.
    Returns a dictionary of text modifications to apply based on emotional state.
    """
    state = get_emotional_state()
    
    modifiers = {
        "punctuation": "normal",  # normal, minimal, excessive
        "emojis": "normal",       # none, minimal, normal, excessive
        "sentiment": "neutral",   # negative, neutral, positive
        "dominant_emotion": None  # most intense current emotion
    }
    
    # Determine dominant emotion
    if state["active_emotions"]:
        dominant = max(state["active_emotions"].items(), 
                       key=lambda x: x[1]["intensity"])
        modifiers["dominant_emotion"] = dominant[0]
    
    # Mood affects sentiment and emojis
    mood = state["mood"]
    if mood < 30:
        modifiers["sentiment"] = "negative"
        modifiers["emojis"] = "minimal"
    elif mood > 70:
        modifiers["sentiment"] = "positive"
        modifiers["emojis"] = "excessive"
    
    # Energy affects punctuation
    energy = state["energy"]
    if energy < 30:
        modifiers["punctuation"] = "minimal"
    elif energy > 70:
        modifiers["punctuation"] = "excessive"
    
    return modifiers

def apply_emotional_style(text):
    """Apply emotional styling to text based on current state."""
    modifiers = get_emotional_tone_modifiers()
    
    # Skip processing for empty text
    if not text or len(text.strip()) == 0:
        return text
    
    # Add emojis based on emotional state
    if modifiers["emojis"] != "none" and len(text) > 5:
        dominant_emotion = modifiers.get("dominant_emotion")
        
        # Emotion-based emoji mapping
        emotion_emojis = {
            "happy": ["😊", "😄", "🙂"],
            "sad": ["😢", "😔", "☹️"],
            "angry": ["😠", "😡"],
            "excited": ["😃", "🤩"],
            "surprised": ["😲", "😮"],
        }
        
        # Default emoji set
        default_emojis = ["😊", "👍"]
        
        # Select emoji set based on dominant emotion
        emoji_set = emotion_emojis.get(dominant_emotion, default_emojis)
        
        # Add emoji with probability based on state
        emoji_prob = 0.1  # Default
        if modifiers["emojis"] == "excessive":
            emoji_prob = 0.5
        elif modifiers["emojis"] == "minimal":
            emoji_prob = 0.05
            
        if random.random() < emoji_prob:
            if not text.endswith(tuple([".", "!", "?"])):
                text += "."
            text += " " + random.choice(emoji_set)
    
    # Adjust punctuation based on energy level
    if modifiers["punctuation"] == "excessive" and text.endswith(("!", ".")):
        if random.random() < 0.4:
            if text.endswith("!"):
                text = text[:-1] + "!!"
            elif text.endswith(".") and random.random() < 0.3:
                text = text[:-1] + "!"
    
    return text

def process_message_emotion(message):
    """Analyze message content to update Kate's emotional state."""
    # Default minimal impact
    mood_change = 0
    energy_change = 0
    expressiveness_change = 0
    emotion = None
    emotion_intensity = 0
    
    # Simple keyword-based analysis
    msg_lower = message.lower()
    
    # Detect greeting patterns (small positive impact)
    if any(greeting in msg_lower for greeting in ["hi kate", "hello kate", "hey kate"]):
        mood_change += 2
        energy_change += 1
    
    # Detect positive sentiment
    positive_words = ["thanks", "thank you", "awesome", "great", "love", "appreciate"]
    if any(word in msg_lower for word in positive_words):
        mood_change += 5
        emotion = "happy"
        emotion_intensity = 40
    
    # Detect negative sentiment
    negative_words = ["stupid", "dumb", "hate", "terrible", "awful"]
    if any(word in msg_lower for word in negative_words):
        mood_change -= 10
        emotion = "sad"
        emotion_intensity = 50
    
    # Detect excitement
    excitement_indicators = ["!", "amazing", "wow", "omg", "awesome"]
    excitement_count = sum(msg_lower.count(word) for word in excitement_indicators)
    if excitement_count > 0:
        energy_change += min(8, excitement_count * 2)
        expressiveness_change += min(5, excitement_count)
        
        if excitement_count >= 2:
            emotion = "excited"
            emotion_intensity = min(70, 30 + excitement_count * 10)
    
    # Apply these changes if significant enough
    total_change = abs(mood_change) + abs(energy_change) + abs(expressiveness_change)
    
    if total_change > 5 or emotion_intensity > 30:
        update_emotional_state(
            mood_change=mood_change,
            energy_change=energy_change,
            expressiveness_change=expressiveness_change,
            emotion=emotion,
            emotion_intensity=emotion_intensity
        )
    
    return {
        "mood_change": mood_change,
        "energy_change": energy_change,
        "expressiveness_change": expressiveness_change,
        "emotion": emotion,
        "emotion_intensity": emotion_intensity
    }

# Make sure the emotions file exists
ensure_emotions_file() 