import json

def get_relationship(user_id):
    try:
        with open("memory/relationships.json", "r") as f:
            data = json.load(f)
        return data.get(str(user_id), {})
    except:
        return {}

def get_all_relationships():
    """
    Returns all relationship data in the system.
    """
    try:
        with open("memory/relationships.json", "r") as f:
            data = json.load(f)
        return data
    except:
        return {}

def get_relationship_data(user_id):
    """
    Returns the relationship data as a tuple: (affection, trust, role, ghosted)
    This is a convenience function used by the main script.
    """
    relationship = get_relationship(str(user_id))
    affection = relationship.get("score", 0)
    trust = relationship.get("trust", 0)
    role = relationship.get("role", "unknown")
    ghosted = relationship.get("ghosted", False)
    return affection, trust, role, ghosted

def get_relationship_summary(user_id):
    """
    Returns a user-friendly summary of the relationship stats for display.
    """
    relationship = get_relationship(str(user_id))
    
    if not relationship:
        return "No relationship data found for this user."
    
    affection = relationship.get("score", 0)
    trust = relationship.get("trust", 0)
    role = relationship.get("role", "unknown")
    ghosted = relationship.get("ghosted", False)
    name = relationship.get("name", "Unknown User")
    nicknames = relationship.get("nicknames", [])
    
    # Convert numeric values to descriptive text
    affection_text = "Unknown"
    if affection >= 90:
        affection_text = "Adoration"
    elif affection >= 70:
        affection_text = "Very High"
    elif affection >= 50:
        affection_text = "High"
    elif affection >= 30:
        affection_text = "Moderate"
    elif affection >= 10:
        affection_text = "Low"
    elif affection >= -10:
        affection_text = "Neutral"
    elif affection >= -30:
        affection_text = "Dislike"
    elif affection >= -70:
        affection_text = "Strong Dislike"
    else:
        affection_text = "Hatred"
    
    trust_text = "Unknown"
    if trust >= 90:
        trust_text = "Complete"
    elif trust >= 70:
        trust_text = "Very High"
    elif trust >= 50:
        trust_text = "High"
    elif trust >= 30:
        trust_text = "Moderate"
    elif trust >= 10:
        trust_text = "Low"
    elif trust >= -10:
        trust_text = "Neutral"
    elif trust >= -30:
        trust_text = "Distrust"
    elif trust >= -70:
        trust_text = "Strong Distrust"
    else:
        trust_text = "Complete Distrust"
    
    status = "Ghosted" if ghosted else "Active"
    
    summary = f"📊 Relationship with {name}:\n"
    summary += f"• Affection: {affection_text} ({affection})\n"
    summary += f"• Trust: {trust_text} ({trust})\n"
    summary += f"• Role: {role.capitalize()}\n"
    
    if nicknames:
        summary += f"• Nicknames: {', '.join(nicknames)}\n"
        
    summary += f"• Status: {status}"
    
    return summary

def set_relationship(user_id, affection=None, trust=None, role=None):
    try:
        with open("memory/relationships.json", "r") as f:
            data = json.load(f)
    except:
        data = {}

    uid = str(user_id)
    if uid not in data:
        data[uid] = {"score": 0, "trust": 0, "role": "unknown"}

    if affection is not None:
        data[uid]["score"] = affection
    if trust is not None:
        data[uid]["trust"] = trust
    if role:
        data[uid]["role"] = role

    with open("memory/relationships.json", "w") as f:
        json.dump(data, f, indent=2)

def initialize_relationship(user_id, name=None, affection=0, trust=0, role="friend"):
    """
    Initialize a relationship with a user if one doesn't exist yet.
    If the relationship already exists, this function won't change it.
    """
    try:
        with open("memory/relationships.json", "r") as f:
            data = json.load(f)
    except:
        data = {}
    
    uid = str(user_id)
    if uid not in data:
        data[uid] = {
            "score": affection,
            "trust": trust,
            "role": role
        }
        if name:
            data[uid]["name"] = name
        
        with open("memory/relationships.json", "w") as f:
            json.dump(data, f, indent=2)
        return True
    return False

def get_favorite_user():
    try:
        with open("memory/relationships.json", "r") as f:
            data = json.load(f)
        favorite = max(data.items(), key=lambda x: x[1].get("score", 0))
        return favorite[0] if favorite[1].get("score", 0) > 70 else None
    except:
        return None

def adjust_relationship_scores(user_id, response_content):
    """
    Allow AI to adjust relationship scores based on the conversation.
    This function parses the AI response for relationship adjustments.
    
    Format for adjustments in AI responses: 
    - In the events list, include items with format:
      - "adjust_relationship:trust:+5" or "adjust_relationship:affection:-3" (adjust for current user)
      - "adjust_relationship:trust:+5:username" or "adjust_relationship:affection:-3:username" (adjust for another user)
      - "adjust_relationship:trust:-5:username" or "adjust_relationship:affection:-3:username" (ALWAYS specify username when lowering affection or trust for someone else)
      - "adjust_relationship:role:new_role:username" (change someone's role)
      - "adjust_relationship:nickname:new_nickname:username" (record someone's nickname)
    """
    try:
        # Extract relationship adjustments from events
        adjustments = {}
        target_user_id = str(user_id)  # Default to current user
        role_change = None
        nickname_change = None
        
        try:
            # Try to parse the response as JSON to extract events
            if isinstance(response_content, str):
                try:
                    data = json.loads(response_content)
                    events = data.get("events", [])
                except json.JSONDecodeError:
                    events = []
            else:
                events = response_content.get("events", [])
            
            # Process relationship adjustment events
            for event in events:
                event_str = str(event).lower()
                if event_str.startswith("adjust_relationship:"):
                    parts = event_str.split(":", 3)  # Now supports 4 parts with target user
                    
                    # Get the metric (trust, affection, role, nickname)
                    metric = parts[1].strip() if len(parts) > 1 else ""
                    
                    # Handle different types of adjustments based on metric
                    if metric in ["trust", "affection"] and len(parts) >= 3:
                        try:
                            # Numeric change for trust/affection
                            change = int(parts[2])
                            
                            # Enforce the rule: must specify username when lowering trust/affection for someone else
                            if change < 0 and len(parts) < 4:
                                # Only allow negative adjustments for the current user
                                target_user_id = str(user_id)
                            else:
                                # Check if we have a target user specification
                                if len(parts) == 4:
                                    target = parts[3].strip()
                                    # If this is an ID, use it directly; otherwise try to resolve the username
                                    if target.isdigit():
                                        target_user_id = target
                                    else:
                                        # Try to resolve username to ID using existing relationship data
                                        target_user_id = resolve_user_by_name(target) or str(user_id)
                                else:
                                    target_user_id = str(user_id)  # Current user
                                
                            adjustments[metric] = change
                        except ValueError:
                            continue
                    elif metric == "role" and len(parts) == 4:
                        # Role change: adjust_relationship:role:new_role:username
                        new_role = parts[2].strip()
                        target = parts[3].strip()
                        
                        # Resolve the target user ID
                        if target.isdigit():
                            target_user_id = target
                        else:
                            target_user_id = resolve_user_by_name(target) or str(user_id)
                            
                        role_change = new_role
                    elif metric == "nickname" and len(parts) == 4:
                        # Nickname change: adjust_relationship:nickname:new_nickname:username
                        new_nickname = parts[2].strip()
                        target = parts[3].strip()
                        
                        # Resolve the target user ID
                        if target.isdigit():
                            target_user_id = target
                        else:
                            target_user_id = resolve_user_by_name(target) or str(user_id)
                            
                        nickname_change = new_nickname
        except Exception as e:
            print(f"Error parsing relationship adjustments: {e}")
            return False
        
        # Check if we have any adjustments to make
        if not (adjustments or role_change or nickname_change):
            return False
            
        # Now apply the adjustments
        relationship = get_relationship(target_user_id)
        changes_made = False
        
        # Get the name for logging/display purposes
        target_name = get_user_name(target_user_id) or f"User {target_user_id}"
        
        # Process trust and affection changes
        if adjustments:
            # Get current values
            current_affection = relationship.get("score", 0)
            current_trust = relationship.get("trust", 0)
            
            # Calculate new values with bounds checking (0-100)
            new_affection = max(0, min(100, current_affection + adjustments.get("affection", 0)))
            new_trust = max(0, min(100, current_trust + adjustments.get("trust", 0)))
            
            # Only update if there's an actual change
            affection_changed = "affection" in adjustments and new_affection != current_affection
            trust_changed = "trust" in adjustments and new_trust != current_trust
            
            if affection_changed or trust_changed:
                affection_param = new_affection if affection_changed else None
                trust_param = new_trust if trust_changed else None
                
                # Call set_relationship to update the values
                set_relationship(target_user_id, affection=affection_param, trust=trust_param)
                changes_made = True
                
                change_desc = []
                if affection_changed:
                    change_dir = "+" if new_affection > current_affection else "-"
                    change_desc.append(f"affection {change_dir}{abs(new_affection - current_affection)}")
                if trust_changed:
                    change_dir = "+" if new_trust > current_trust else "-"
                    change_desc.append(f"trust {change_dir}{abs(new_trust - current_trust)}")
                    
                print(f"AI adjusted relationship with {target_name} (ID: {target_user_id}): {', '.join(change_desc)}")
        
        # Process role change
        if role_change:
            current_role = relationship.get("role", "unknown")
            
            # Handle boyfriend/girlfriend proposals differently - require explicit proposal
            if role_change in ["boyfriend", "girlfriend"] and current_role != role_change:
                # For these special roles, don't auto-assign them in memory evaluation
                # Instead, check if this is a direct proposal from the user
                current_affection = relationship.get("score", 0)
                current_trust = relationship.get("trust", 0)
                
                # Automatically accept if affection is at maximum (100)
                if current_affection >= 100:
                    set_relationship(target_user_id, role=role_change)
                    print(f"AI automatically accepted {target_name}'s request to be {role_change} due to maximum affection")
                    changes_made = True
                # Accept if affection and trust are high enough
                elif current_affection >= 90 and current_trust >= 80:
                    set_relationship(target_user_id, role=role_change)
                    print(f"AI accepted {target_name}'s request to be {role_change}")
                    changes_made = True
                else:
                    # Don't change role if scores aren't high enough
                    print(f"AI rejected {target_name}'s request to be {role_change} due to insufficient affection/trust")
            else:
                # Handle all other role changes normally
                if role_change != current_role:
                    set_relationship(target_user_id, role=role_change)
                    print(f"AI changed {target_name}'s role from '{current_role}' to '{role_change}'")
                    changes_made = True
        
        # Process nickname change
        if nickname_change:
            try:
                # Load full data to update nickname
                with open("memory/relationships.json", "r") as f:
                    data = json.load(f)
                
                # Initialize user record if it doesn't exist
                if str(target_user_id) not in data:
                    data[str(target_user_id)] = {"score": 0, "trust": 0, "role": "unknown"}
                
                # Initialize or update nicknames list
                if "nicknames" not in data[str(target_user_id)]:
                    data[str(target_user_id)]["nicknames"] = []
                
                # Add nickname if it's not already in the list
                if nickname_change not in data[str(target_user_id)]["nicknames"]:
                    data[str(target_user_id)]["nicknames"].append(nickname_change)
                    
                    # Save updated data
                    with open("memory/relationships.json", "w") as f:
                        json.dump(data, f, indent=2)
                    
                    print(f"AI added nickname '{nickname_change}' for {target_name}")
                    changes_made = True
            except Exception as e:
                print(f"Error updating nickname: {e}")
        
        return changes_made
    except Exception as e:
        print(f"Error in adjust_relationship_scores: {e}")
        return False

def resolve_user_by_name(username):
    """
    Try to resolve a username to a user ID using the existing relationship data.
    This checks both names and nicknames.
    Returns None if no match is found.
    """
    try:
        with open("memory/relationships.json", "r") as f:
            data = json.load(f)
            
        username_lower = username.lower()
        
        # First check exact name matches
        for user_id, info in data.items():
            if info.get("name", "").lower() == username_lower:
                return user_id
                
        # Then check nicknames
        for user_id, info in data.items():
            if "nicknames" in info:
                for nickname in info["nicknames"]:
                    if nickname.lower() == username_lower:
                        return user_id
                
        return None
    except:
        return None

def get_user_name(user_id):
    """
    Get a user's name from the relationship data.
    Returns None if the user is not found.
    """
    try:
        with open("memory/relationships.json", "r") as f:
            data = json.load(f)
        
        user_data = data.get(str(user_id), {})
        return user_data.get("name")
    except:
        return None

def get_user_nicknames(user_id):
    """
    Get a list of nicknames for a user.
    Returns an empty list if the user has no recorded nicknames.
    """
    try:
        with open("memory/relationships.json", "r") as f:
            data = json.load(f)
        
        user_data = data.get(str(user_id), {})
        return user_data.get("nicknames", [])
    except:
        return []

def get_speaking_style(user_id):
    """
    Determines the appropriate speaking style based on relationship levels.
    Returns a dictionary with tone guidelines and style parameters.
    
    Speaking styles are determined by:
    - Affection level (formal/informal, emotional distance)
    - Trust level (guarded/open communication)
    - Role (context-specific language)
    
    This function helps Kate adjust her communication style dynamically.
    """
    affection, trust, role, ghosted = get_relationship_data(str(user_id))
    name = get_user_name(user_id) or "User"
    
    # Base style dictionary
    style = {
        "formality": "neutral",
        "openness": "neutral",
        "emotional_tone": "neutral",
        "role_specific": "generic",
        "use_emoji": True,
        "use_nicknames": False,
        "personal_disclosures": "minimal"
    }
    
    # Adjust formality based on affection and role
    if affection >= 70:
        style["formality"] = "very casual"
        style["use_emoji"] = True
        style["use_nicknames"] = True
    elif affection >= 50:
        style["formality"] = "casual"
        style["use_emoji"] = True
    elif affection >= 30:
        style["formality"] = "friendly"
    elif affection <= -30:
        style["formality"] = "distant"
        style["use_emoji"] = False
        
    # Adjust openness based on trust
    if trust >= 70:
        style["openness"] = "very open"
        style["personal_disclosures"] = "substantial"
    elif trust >= 50:
        style["openness"] = "open"
        style["personal_disclosures"] = "moderate"
    elif trust >= 30:
        style["openness"] = "somewhat open"
    elif trust <= -10:
        style["openness"] = "guarded"
        style["personal_disclosures"] = "none"
    elif trust <= -50:
        style["openness"] = "very guarded"
        
    # Adjust emotional tone based on affection
    if affection >= 70:
        style["emotional_tone"] = "warm"
    elif affection >= 40:
        style["emotional_tone"] = "friendly"
    elif affection >= 20:
        style["emotional_tone"] = "polite"
    elif affection <= -20:
        style["emotional_tone"] = "cool"
    elif affection <= -50:
        style["emotional_tone"] = "cold"
        
    # Role-specific adjustments
    if role == "friend":
        style["role_specific"] = "friend"
        if affection >= 60:
            style["use_nicknames"] = True
    elif role == "best_friend":
        style["role_specific"] = "best_friend"
        style["formality"] = "very casual"
        style["openness"] = "very open"
        style["use_nicknames"] = True
    elif role == "colleague":
        style["role_specific"] = "colleague"
        style["formality"] = max(style["formality"], "friendly")  # Not too casual
    elif role == "family":
        style["role_specific"] = "family"
        style["formality"] = "casual"
    elif role == "romantic":
        style["role_specific"] = "romantic"
        style["emotional_tone"] = "affectionate"
        style["use_nicknames"] = True
    elif role == "authority":
        style["role_specific"] = "authority"
        style["formality"] = "formal"
        style["use_emoji"] = False
        
    # Get available nicknames
    nicknames = get_user_nicknames(user_id)
    if nicknames and style["use_nicknames"]:
        style["preferred_nickname"] = nicknames[0]  # Use first nickname by default
    else:
        style["preferred_nickname"] = name
        
    # Generate tone description to guide response generation
    style["tone_description"] = generate_tone_description(style)
    
    return style

def generate_tone_description(style):
    """
    Generates a natural language description of the speaking style to guide Kate's responses.
    """
    tone_desc = []
    
    # Formality
    if style["formality"] == "very casual":
        tone_desc.append("Be very casual and relaxed")
    elif style["formality"] == "casual":
        tone_desc.append("Use a casual, everyday tone")
    elif style["formality"] == "friendly":
        tone_desc.append("Be friendly and approachable")
    elif style["formality"] == "formal":
        tone_desc.append("Maintain a formal, professional tone")
    elif style["formality"] == "distant":
        tone_desc.append("Keep a respectful distance")
        
    # Openness
    if style["openness"] == "very open":
        tone_desc.append("be very open about thoughts and feelings")
    elif style["openness"] == "open":
        tone_desc.append("share thoughts openly")
    elif style["openness"] == "guarded":
        tone_desc.append("be careful about sharing personal information")
    elif style["openness"] == "very guarded":
        tone_desc.append("avoid sharing personal thoughts and information")
        
    # Emotional tone
    if style["emotional_tone"] == "warm":
        tone_desc.append("show warmth and enthusiasm")
    elif style["emotional_tone"] == "friendly":
        tone_desc.append("be upbeat and friendly")
    elif style["emotional_tone"] == "cool":
        tone_desc.append("keep emotions neutral and controlled")
    elif style["emotional_tone"] == "cold":
        tone_desc.append("be emotionally distant")
        
    # Role-specific
    if style["role_specific"] == "friend":
        tone_desc.append("talk like a friend")
    elif style["role_specific"] == "best_friend":
        tone_desc.append("talk like a close friend who shares everything")
    elif style["role_specific"] == "colleague":
        tone_desc.append("talk like a friendly co-worker")
    elif style["role_specific"] == "family":
        tone_desc.append("talk like a family member")
    elif style["role_specific"] == "romantic":
        tone_desc.append("talk with affection and care")
    elif style["role_specific"] == "authority":
        tone_desc.append("speak with authority and expertise")
        
    # Emoji usage
    if style["use_emoji"]:
        tone_desc.append("use occasional emojis when appropriate")
    else:
        tone_desc.append("avoid using emojis")
        
    # Nickname usage
    if style["use_nicknames"] and "preferred_nickname" in style:
        if style["preferred_nickname"] != "User":
            tone_desc.append(f"call them {style['preferred_nickname']}")
        
    # Join with commas and 'and'
    if len(tone_desc) > 1:
        return f"{', '.join(tone_desc[:-1])}, and {tone_desc[-1]}"
    elif tone_desc:
        return tone_desc[0]
    else:
        return "Use a neutral, balanced tone"