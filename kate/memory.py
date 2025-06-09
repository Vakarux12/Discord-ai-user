import json
import openai
import os
import re
import random
from datetime import datetime, timedelta
import traceback

seen_messages = set()
last_memory_conversion = datetime.now()  # Track when the last memory conversion happened
memory_storage_chance = 0.6  # Only 60% chance of storing a message in memory
memory_conversion_interval = 1800  # 30 minutes between memory conversions (increased from 10 minutes)

def has_seen_message(message_id):
    return message_id in seen_messages

def mark_message_seen(message_id):
    seen_messages.add(message_id)

def update_memory(message):
    # Random chance to skip memory storage entirely
    if 0.1 > memory_storage_chance:
        print(f"[{datetime.now().isoformat()}] Skipped memory storage for message: {message.id}")
        return

    try:
        with open("memory/short_term.json", "r") as f:
            memory = json.load(f)
    except:
        memory = {}

    channel_id = str(message.channel.id)
    now = datetime.now().isoformat()

    if channel_id not in memory:
        memory[channel_id] = []

    # Check for duplicate content before adding
    content = message.content
    author = message.author.name
    
    # More aggressive duplicate detection - check last 10 messages and 30 second window
    
    # Also skip very short messages under 10 characters unless they mention Kate
    if len(content) < 1 and "kate" not in content.lower():
        # 80% chance to skip short messages
        if random.random() < 0.8:
            print(f"[{datetime.now().isoformat()}] Skipped short message: {content}")
            return
    is_duplicate = False
    if not is_duplicate:
        # Add the new message to memory
        memory[channel_id].append({
            "author": message.author.name,
            "user_id": str(message.author.id),
            "content": message.content,
            "timestamp": now
        })

        with open("memory/short_term.json", "w") as f:
            json.dump(memory, f, indent=2)
    
    # Check if we should convert to long-term memory - now less frequent
    global last_memory_conversion
    if (datetime.now() - last_memory_conversion).total_seconds() > memory_conversion_interval:  # 30 minutes
        print(f"[{datetime.now().isoformat()}] Scheduled memory conversion starting")
        # Clean up duplicates before converting
        deduplicate_short_term_memory()
        convert_to_long_term_memory()
        # Also explicitly clear short-term memory to ensure it doesn't grow too large
        clear_short_term_memory(keep_last_n=6)  # Keep more recent messages since conversion is less frequent
        last_memory_conversion = datetime.now()

def deduplicate_short_term_memory():
    """
    Removes duplicate entries from the short-term memory file
    """
    try:
        with open("memory/short_term.json", "r") as f:
            memory = json.load(f)
        
        cleaned_memory = {}
        
        for channel_id, messages in memory.items():
            # Use a set to track unique message fingerprints
            seen_messages = set()
            cleaned_messages = []
            
            for msg in messages:
                # Create a fingerprint from content, author and approximate time (rounded to nearest minute)
                try:
                    timestamp = datetime.fromisoformat(msg.get("timestamp", "")).replace(second=0, microsecond=0).isoformat()
                except:
                    timestamp = "unknown"
                    
                fingerprint = f"{msg.get('author')}:{msg.get('content')}:{timestamp}"
                
                if fingerprint not in seen_messages:
                    seen_messages.add(fingerprint)
                    cleaned_messages.append(msg)
            
            cleaned_memory[channel_id] = cleaned_messages
        
        # Save the cleaned memory
        with open("memory/short_term.json", "w") as f:
            json.dump(cleaned_memory, f, indent=2)
            
        print(f"[{datetime.now().isoformat()}] Short-term memory deduplication complete")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Short-term memory deduplication error: {e}")

def load_short_term(channel_id):
    try:
        with open("memory/short_term.json", "r") as f:
            memory = json.load(f)
    except:
        return []

    now = datetime.now()
    result = []
    channel_msgs = memory.get(str(channel_id), [])
    
    # Only return the last 4 messages to keep context focused
    for entry in channel_msgs[-4:]:
        try:
            msg_time = datetime.fromisoformat(entry["timestamp"])
            if now - msg_time <= timedelta(minutes=15):
                # Correctly identify if message is from Kate or another user
                role = "assistant" if entry.get("user_id") == "kate" or entry.get("author", "").lower() == "kate" else "user"
                result.append({"role": role, "content": entry["content"]})
        except Exception as e:
            print(f"Error loading short-term memory: {e}")
            continue
    return result

def convert_to_long_term_memory():
    """
    Converts short-term memory to long-term memory by summarizing conversations
    and storing them in the long-term memory file.
    This process is now more selective about what gets stored permanently.
    """
    try:
        # Load short-term memory
        with open("memory/short_term.json", "r") as f:
            short_term = json.load(f)
        
        # Load long-term memory
        try:
            with open("memory/long_term.json", "r") as f:
                long_term = json.load(f)
        except:
            long_term = {}
            
        # Create long_term.json if it doesn't exist
        if not os.path.exists("memory/long_term.json"):
            with open("memory/long_term.json", "w") as f:
                json.dump({}, f)
        
        now = datetime.now()
        threshold = now - timedelta(minutes=30)  # Messages older than 30 minutes (increased from 10)
        
        # Keep track of users in this batch for relationship evaluation
        users_in_conversations = set()
        
        # Process each channel
        for channel_id, messages in short_term.items():
            if channel_id not in long_term:
                long_term[channel_id] = []
            
            # Organize messages by time chunks (30 minute blocks instead of 10 minute blocks)
            chunks = {}
            updated_messages = []
            
            for msg in messages:
                try:
                    msg_time = datetime.fromisoformat(msg["timestamp"])
                    
                    # Keep only very recent messages in short-term memory
                    if msg_time > threshold:
                        updated_messages.append(msg)
                        continue
                    
                    # Track user information for built-in memory - only if message is substantial
                    user_id = msg.get("user_id", "unknown")
                    content = msg.get("content", "")
                    
                    # Skip tracking low-value messages (e.g., very short messages)
                    if len(content) < 15 and random.random() < 0.7:
                        continue
                        
                    if user_id != "unknown":
                        # Track this user for relationship evaluation
                        users_in_conversations.add(user_id)
                        
                        # Update user encounter information - with randomized chance to skip
                        if random.random() > 0.3:  # 70% chance to count encounter
                            if "user_info" not in long_term:
                                long_term["user_info"] = {}
                            
                            if user_id not in long_term["user_info"]:
                                long_term["user_info"][user_id] = {
                                    "name": msg.get("author", "User"),
                                    "first_seen": msg_time.isoformat(),
                                    "last_seen": msg_time.isoformat(),
                                    "channels": [channel_id],
                                    "topics": [],
                                    "encounters": 1
                                }
                            else:
                                user_data = long_term["user_info"][user_id]
                                user_data["last_seen"] = msg_time.isoformat()
                                user_data["encounters"] = user_data.get("encounters", 0) + 1
                                if channel_id not in user_data.get("channels", []):
                                    user_data.setdefault("channels", []).append(channel_id)
                    
                    # Group older messages by hour for summarization
                    chunk_key = msg_time.strftime("%Y-%m-%d %H")
                    if chunk_key not in chunks:
                        chunks[chunk_key] = []
                    
                    chunks[chunk_key].append(msg)
                except:
                    # Only keep messages with valid timestamps in short-term
                    if "timestamp" in msg and is_valid_timestamp(msg["timestamp"]):
                        updated_messages.append(msg)
            
            # Update short-term memory to only include recent messages
            # Keep only the most recent messages (max 20) to prevent overflow
            short_term[channel_id] = updated_messages[-20:] if len(updated_messages) > 20 else updated_messages
            
            # Summarize each chunk of older messages
            for chunk_key, chunk_messages in chunks.items():
                if not chunk_messages:
                    continue
                
                # Create conversation text for summarization
                conversation = ""
                participants = set()
                user_ids = set()
                
                for msg in chunk_messages:
                    author = msg.get('author', 'Unknown')
                    participants.add(author)
                    user_id = msg.get('user_id', 'unknown')
                    if user_id != 'unknown':
                        user_ids.add(user_id)
                    conversation += f"{author}: {msg.get('content', '')}\n"
                
                # Only summarize if there's a meaningful conversation
                # Increased minimum threshold for what constitutes a meaningful conversation
                if len(conversation.strip()) < 100 or len(chunk_messages) < 3:
                    # For shorter conversations, random chance to still record
                    if random.random() > 0.15:  # 85% chance to skip short conversations
                        continue
                
                # Only summarize if there's significant interaction (multiple messages)
                if len(participants) < 2 and random.random() > 0.2:  # 80% chance to skip monologues
                    continue
                    
                # Additional check: skip if there's no emotional or important content
                important_terms = ["feel", "think", "believe", "love", "hate", "angry", "happy", "sad", 
                                  "hope", "dream", "wish", "plan", "want", "need", "sorry", "thank", 
                                  "please", "help", "important", "secret", "never", "always", "promise"]
                
                has_important_content = any(term in conversation.lower() for term in important_terms)
                if not has_important_content and random.random() > 0.3:  # 70% chance to skip non-important conversations
                    continue
                
                # Summarize using GPT
                summary = summarize_conversation(conversation)
                
                # Extract topics from the conversation
                topics = extract_topics(conversation)
                
                # Update user topics
                for user_id in user_ids:
                    if user_id in long_term.get("user_info", {}) and topics:
                        for topic in topics:
                            if topic not in long_term["user_info"][user_id].get("topics", []):
                                long_term["user_info"][user_id].setdefault("topics", []).append(topic)
                
                # Only add diary entry for significant conversations
                if len(conversation) > 200 or has_important_content:
                    timestamp = datetime.strptime(chunk_key, "%Y-%m-%d %H").isoformat()
                    add_diary_entry(summary, timestamp)
                
                # Add summary to long-term memory
                long_term[channel_id].append({
                    "time_period": chunk_key,
                    "summary": summary,
                    "participants": list(participants),
                    "user_ids": list(user_ids),
                    "topics": topics,
                    "timestamp": datetime.now().isoformat()
                })
        
        # Save updated short-term memory
        with open("memory/short_term.json", "w") as f:
            json.dump(short_term, f, indent=2)
        
        # Save updated long-term memory
        with open("memory/long_term.json", "w") as f:
            json.dump(long_term, f, indent=2)
            
        # After processing memory, evaluate relationships using OpenAI
        try:
            for user_id in [uid for uid in users_in_conversations if uid != "unknown"]:
                user_info = long_term.get("user_info", {}).get(user_id, {})
                if user_info:
                    name = user_info.get("name", "User")
                    print(f"Evaluating relationship with {name} ({user_id}) from memory")
                    # This will be implemented by the OpenAI analysis during regular interactions
        except Exception as e:
            print(f"Error evaluating relationships: {e}")
            traceback.print_exc()
        
        print(f"[{datetime.now().isoformat()}] Memory conversion complete")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Memory conversion error: {e}")
        traceback.print_exc()

def evaluate_relationship_from_memory(user_id, long_term_memory):
    """
    Analyzes long-term memory for a user to suggest relationship adjustments
    This allows for organic relationship growth based on conversation history
    """
    try:
        from kate.trust_graph import get_relationship, set_relationship
        
        # Get current relationship data
        relationship = get_relationship(str(user_id))
        if not relationship:
            return  # No relationship established yet
        
        # Get user info
        user_info = long_term_memory.get("user_info", {}).get(str(user_id), {})
        if not user_info:
            return  # No user info in memory
            
        # Extract user's recent memories
        user_memories = []
        for channel_id, memories in long_term_memory.items():
            if channel_id == "user_info":
                continue
                
            for memory in memories:
                if str(user_id) in memory.get("user_ids", []):
                    user_memories.append(memory.get("summary", ""))
        
        # Only analyze if we have enough memories (at least 2)
        if len(user_memories) < 2:
            return
            
        # Limit to most recent 5 memories to keep context manageable
        recent_memories = user_memories[-5:]
        memory_text = "\n".join(recent_memories)
        
        # Get current values
        current_affection = relationship.get("score", 0)
        current_trust = relationship.get("trust", 0)
        role = relationship.get("role", "unknown")
        
        # Use AI to evaluate relationship based on memory
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": 
                     f"""You are an AI that analyzes conversations to determine relationship changes.
                     Based solely on these memories, suggest subtle changes to relationship metrics.
                     Current stats: Affection={current_affection}, Trust={current_trust}, Role={role}
                     
                     Guidelines:
                     - Changes should be subtle (-2 to +2 range typically)
                     - Only suggest changes if there's clear evidence in the memories
                     - Be conservative; major shifts should happen over time
                     - If nothing notable happened, don't suggest any changes
                     
                     Return a JSON object with suggested changes (or null if no change):
                     {{"affection_change": int_or_null, "trust_change": int_or_null, "reason": "brief explanation"}}"""},
                    {"role": "user", "content": f"Analyze these memories about interactions with this user:\n\n{memory_text}"}
                ],
                max_tokens=150,
                temperature=0.3
            )
            
            result = response.choices[0].message.content.strip()
            try:
                # Parse the suggested changes
                changes = json.loads(result)
                
                affection_change = changes.get("affection_change")
                trust_change = changes.get("trust_change")
                reason = changes.get("reason", "Based on recent interactions")
                
                # Apply changes if any were suggested
                if affection_change is not None or trust_change is not None:
                    # Calculate new values with bounds checking (0-100)
                    new_affection = None
                    new_trust = None
                    
                    if affection_change is not None:
                        new_affection = max(0, min(100, current_affection + affection_change))
                    
                    if trust_change is not None:
                        new_trust = max(0, min(100, current_trust + trust_change))
                        
                    # Check if relationship should progress based on high scores
                    suggested_role = None
                    if (new_affection is not None and new_affection >= 80) and (new_trust is not None and new_trust >= 70):
                        if role == "friend":
                            # Progress from friend to crush with high scores
                            suggested_role = "crush"
                    elif (new_affection is not None and new_affection >= 60) and (new_trust is not None and new_trust >= 50):
                        if role == "stranger":
                            # Progress from stranger to friend with decent scores
                            suggested_role = "friend"
                    
                    # Update relationship with new values and possibly new role
                    set_relationship(
                        user_id, 
                        affection=new_affection, 
                        trust=new_trust,
                        role=suggested_role
                    )
                    
                    print(f"Updated relationship with user {user_id}: {reason}")
                    if affection_change is not None:
                        print(f"Affection: {current_affection} → {new_affection} ({affection_change:+})")
                    if trust_change is not None:
                        print(f"Trust: {current_trust} → {new_trust} ({trust_change:+})")
                    if suggested_role:
                        print(f"Role: {role} → {suggested_role}")
                    
                    # Add a diary entry about the changing relationship
                    name = user_info.get("name", "that person")
                    if abs(affection_change or 0) > 1 or abs(trust_change or 0) > 1:
                        diary_entry = f"I feel like my relationship with {name} is changing. {reason}"
                        add_diary_entry(diary_entry)
            except:
                pass  # Failed to parse the AI's response
        except Exception as e:
            print(f"Error in relationship evaluation: {e}")
    except Exception as e:
        print(f"Error in relationship evaluation: {e}")

def is_valid_timestamp(timestamp_str):
    """Check if a timestamp string is valid"""
    try:
        datetime.fromisoformat(timestamp_str)
        return True
    except:
        return False

def extract_topics(conversation_text):
    """Extract key topics from a conversation"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": 
                 "Extract 1-3 key topics from this conversation. Return only a comma-separated list of short phrases (2-3 words each)."},
                {"role": "user", "content": conversation_text}
            ],
            max_tokens=50,
            temperature=0.3
        )
        
        topics_text = response.choices[0].message.content.strip()
        topics = [topic.strip() for topic in topics_text.split(',')]
        return topics
    except Exception as e:
        print(f"Topic extraction error: {e}")
        return []

def summarize_conversation(conversation_text):
    """
    Use GPT to summarize a conversation into a concise memory
    """
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": 
                 "You are an AI assistant that summarizes conversations. Create a concise summary of the following conversation that captures key points, emotional moments, and important information. The summary should be written in first person perspective, as if a participant named Kate is recalling what happened."},
                {"role": "user", "content": conversation_text}
            ],
            max_tokens=200,
            temperature=0.7
        )
        
        summary = response.choices[0].message.content.strip()
        return summary
    except Exception as e:
        print(f"Summarization error: {e}")
        return f"Conversation about {len(conversation_text)} characters. (Failed to summarize)"

def get_long_term_memory(channel_id, limit=3):
    """
    Retrieves relevant long-term memories for a given channel
    Limit to control token usage
    """
    try:
        with open("memory/long_term.json", "r") as f:
            long_term = json.load(f)
        
        memories = long_term.get(str(channel_id), [])
        
        # Sort by timestamp (newest first) and return limited memories
        sorted_memories = sorted(memories, key=lambda x: x.get("timestamp", ""), reverse=True)
        return sorted_memories[:limit]
    except:
        return []

def get_memory_context(channel_id, user_id=None):
    """
    Combines short and long-term memory to create an optimized context for responses
    Includes relevant user information if available
    Now with more selective memory retrieval to reduce information overload
    """
    # Get short-term context (last few messages)
    short_term = load_short_term(channel_id)
    
    # Random chance (25%) to provide minimal context and rely on short-term only
    if random.random() < 0.25:
        return short_term
    
    # Get relevant long-term memories (limited to 2 for token efficiency)
    long_term = get_long_term_memory(channel_id, limit=2)
    
    # Filter out less important memories
    filtered_long_term = []
    for memory in long_term:
        # Skip memories that don't mention the current user
        if user_id and str(user_id) not in memory.get("user_ids", []):
            # 80% chance to skip memories not involving this user
            if random.random() < 0.8:
                continue
        
        # Check if memory seems important
        summary = memory.get("summary", "")
        important_terms = ["feel", "think", "believe", "love", "hate", "angry", "happy", "sad", 
                          "hope", "dream", "wish", "plan", "want", "need", "sorry", "thank", 
                          "important", "secret", "never", "always", "promise"]
        
        has_important_content = any(term in summary.lower() for term in important_terms)
        
        # If not important, 60% chance to skip
        if not has_important_content and random.random() < 0.6:
            continue
            
        filtered_long_term.append(memory)
    
    # Build context with optimized token usage
    context = []
    
    # Add user information if available, but with random chance to be more forgetful
    if user_id and random.random() > 0.3:  # 70% chance to include user info
        user_info = get_user_info(user_id)
        if user_info:
            # Create a compact user info string
            name = user_info.get("name", "Unknown")
            encounters = user_info.get("encounters", 0)
            
            # Only include topics if there are meaningful ones and not too many interactions
            # If you've talked to someone a lot, you don't need to be reminded of the topics
            if encounters < 10 or random.random() < 0.3:  # Only 30% chance if many encounters
                topics = user_info.get("topics", [])[:2]  # Limit to fewer topics
                
                user_context = f"About {name}: "
                
                # 30% chance to "forget" the exact number of encounters
                if random.random() < 0.3 and encounters > 5:
                    user_context += f"We've talked several times before. "
                else:
                    user_context += f"Talked {encounters} times before. "
                    
                if topics:
                    user_context += f"Topics: {', '.join(topics)}."
                    
                context.append({"role": "system", "content": user_context})
    
    # Add long-term memories if available (compact format)
    if filtered_long_term:
        # 40% chance to include only one memory even if more are available
        if len(filtered_long_term) > 1 and random.random() < 0.4:
            filtered_long_term = [filtered_long_term[0]]
            
        memory_text = "Relevant past interactions:\n"
        for memory in filtered_long_term:
            # Use shorter summary format
            memory_text += f"• {memory.get('summary', '')}\n"
        
        context.append({"role": "system", "content": memory_text})
    
    # Add recent diary entry with only 50% chance
    if random.random() < 0.5:
        recent_diary = get_recent_diary_entry()
        if recent_diary:
            context.append({"role": "system", "content": f"A note you wrote recently: {recent_diary}"})
    
    # Add short-term context (recent messages)
    context.extend(short_term)
    
    return context

def get_user_info(user_id):
    """Get information about a user from long-term memory"""
    try:
        with open("memory/long_term.json", "r") as f:
            long_term = json.load(f)
        
        return long_term.get("user_info", {}).get(str(user_id), None)
    except:
        return None

def has_talked_to_user(user_id):
    """
    Check if Kate has talked to a specific user before
    Returns a boolean and relevant information in a natural format
    """
    user_info = get_user_info(str(user_id))
    if user_info:
        # Get memories with this user
        user_memories = []
        try:
            with open("memory/long_term.json", "r") as f:
                long_term = json.load(f)
            
            for channel_id, memories in long_term.items():
                if channel_id in ["user_info", "diary"]:
                    continue
                
                for memory in memories:
                    if str(user_id) in memory.get("user_ids", []):
                        user_memories.append(memory)
            
            # Sort by timestamp (newest first)
            user_memories = sorted(user_memories, key=lambda x: x.get("timestamp", ""), reverse=True)
        except:
            pass
        
        # Format user info with memories
        user_data = {
            "name": user_info.get("name", "Unknown"),
            "memories": user_memories[:3],  # Limit to 3 most recent memories
            "topics": user_info.get("topics", []),
            "encounters": user_info.get("encounters", 0),
            "first_seen": user_info.get("first_seen", ""),
            "last_seen": user_info.get("last_seen", "")
        }
        
        return True, user_data
    return False, None

def add_diary_entry(text, timestamp=None):
    """
    Add an entry to Kate's diary
    Now with more selectivity to avoid filling the diary with mundane entries
    """
    try:
        # Skip empty or very short entries
        if not text or len(text.strip()) < 20:
            print(f"[{datetime.now().isoformat()}] Skipped adding short diary entry: {text[:20]}...")
            return False
            
        # Skip duplicate-like entries (if already in the diary)
        try:
            with open("memory/diary.json", "r") as f:
                diary = json.load(f)
                
            # Check for similar entries in the last 5 entries
            for entry in diary[-5:]:
                existing_text = entry.get("entry", "")
                # Simple similarity check - if 70% of words are the same
                existing_words = set(existing_text.lower().split())
                new_words = set(text.lower().split())
                
                if len(existing_words) > 0 and len(new_words) > 0:
                    common_words = existing_words.intersection(new_words)
                    similarity = len(common_words) / min(len(existing_words), len(new_words))
                    
                    if similarity > 0.7:
                        print(f"[{datetime.now().isoformat()}] Skipped similar diary entry: {text[:30]}...")
                        return False
        except:
            diary = []
            
        # Random chance to skip entries - 40% chance to skip any entry
        if random.random() > 0.6:
            print(f"[{datetime.now().isoformat()}] Randomly skipped diary entry: {text[:30]}...")
            return False
            
        if timestamp is None:
            timestamp = datetime.now().isoformat()

        # Load existing diary
        try:
            with open("memory/diary.json", "r") as f:
                diary = json.load(f)
        except:
            diary = []
        
        # Add new entry
        diary.append({
            "timestamp": timestamp,
            "entry": text
        })
        
        # Limit diary size - keep only the most recent 50 entries
        if len(diary) > 50:
            diary = diary[-50:]
        
        # Save updated diary
        with open("memory/diary.json", "w") as f:
            json.dump(diary, f, indent=2)
            
        print(f"[{datetime.now().isoformat()}] Added diary entry: {text[:30]}...")
        return True
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error adding diary entry: {e}")
        return False

def get_recent_diary_entry():
    """
    Get a recent diary entry with selective filtering and randomness
    This makes Kate's memory recall more human-like with occasional forgetfulness
    """
    try:
        # 30% chance to skip returning any diary entry - simulate forgetting
        if random.random() < 0.3:
            print(f"[{datetime.now().isoformat()}] Randomly skipped recalling any diary entry")
            return None
    
        with open("memory/diary.json", "r") as f:
            diary = json.load(f)
        
        if not diary:
            return None
            
        # 30% chance to get a completely random entry rather than most recent
        if random.random() < 0.3 and len(diary) > 5:
            # Pick a random entry from the most recent 5-15 entries
            max_index = min(15, len(diary))
            random_index = random.randint(0, max_index-1)
            return diary[random_index].get("entry", "")
            
        # Get the 3 most recent entries
        recent_entries = diary[:3]
        
        # Choose the most emotional/impactful entry from recent ones
        important_terms = ["feel", "think", "believe", "love", "hate", "angry", "happy", "sad", 
                          "hope", "dream", "wish", "plan", "want", "need", "sorry", "thank", 
                          "important", "secret", "never", "always", "promise"]
                          
        # Score each entry based on emotional/important content
        scored_entries = []
        for entry in recent_entries:
            text = entry.get("entry", "")
            score = 0
            
            # Count important terms
            for term in important_terms:
                if term in text.lower():
                    score += 1
                    
            # Longer entries might be more significant
            score += min(len(text) / 100, 2)  # Maximum +2 points for length
            
            scored_entries.append((score, text))
            
        # Sort by score and return the highest scoring entry
        scored_entries.sort(reverse=True)
        if scored_entries:
            return scored_entries[0][1]
        
        # Fallback to most recent entry
        return diary[0].get("entry", "")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error getting diary entry: {e}")
        return None

def get_diary_entries(days=7, limit=5):
    """
    Get diary entries from the past X days, limited to save tokens
    Now with more selective filtering to focus on meaningful entries
    """
    try:
        with open("memory/diary.json", "r") as f:
            diary = json.load(f)
        
        # Calculate cutoff date
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        # Filter entries by date
        possible_entries = []
        for entry in diary:
            if entry.get("timestamp", "") >= cutoff:
                possible_entries.append(entry)
                
        # If we have more entries than our limit, prioritize important ones
        if len(possible_entries) > limit:
            # Score entries by importance
            important_terms = ["feel", "think", "believe", "love", "hate", "angry", "happy", "sad", 
                              "hope", "dream", "wish", "plan", "want", "need", "sorry", "thank", 
                              "important", "secret", "never", "always", "promise"]
                              
            scored_entries = []
            for entry in possible_entries:
                text = entry.get("entry", "")
                score = 0
                
                # Count important terms
                for term in important_terms:
                    if term in text.lower():
                        score += 1
                        
                # Newer entries get a recency bonus
                try:
                    entry_time = datetime.fromisoformat(entry.get("timestamp", ""))
                    days_old = (datetime.now() - entry_time).total_seconds() / (24 * 3600)
                    recency_score = max(0, 5 - days_old)  # Maximum +5 points for very recent entries
                    score += recency_score
                except:
                    pass
                
                scored_entries.append((score, entry))
                
            # Sort by score (highest first)
            scored_entries.sort(reverse=True)
            
            # Take the top entries up to the limit
            # But also add some randomness - 30% chance to include a random lower-scored entry
            selected_entries = [entry for _, entry in scored_entries[:limit-1]]
            
            if len(scored_entries) > limit and random.random() < 0.3:
                # Pick a random entry from the rest
                random_index = random.randint(limit, len(scored_entries)-1)
                selected_entries.append(scored_entries[random_index][1])
            else:
                # Add the next highest scored entry
                if len(scored_entries) >= limit:
                    selected_entries.append(scored_entries[limit-1][1])
                    
            return selected_entries
        else:
            # If we have fewer entries than the limit, return all of them
            return possible_entries
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error getting diary entries: {e}")
        return []

def search_memory(query, user_id=None, max_results=2):
    """
    Search long-term memory for relevant information
    Optimized to reduce token usage by limiting results
    """
    try:
        with open("memory/long_term.json", "r") as f:
            long_term = json.load(f)
            
        results = []
        query_lower = query.lower()
        keywords = re.findall(r'\b\w+\b', query_lower)
        
        # If looking for a specific user
        if user_id:
            return has_talked_to_user(user_id)
        else:
            # Search across all channels for keyword matches
            for channel_id, memories in long_term.items():
                if channel_id in ["user_info", "diary"]:
                    continue
                    
                for memory in memories:
                    summary = memory.get("summary", "").lower()
                    # Check if any keyword matches
                    if any(keyword in summary for keyword in keywords):
                        results.append({
                            "channel_id": channel_id,
                            "memory": memory
                        })
                        if len(results) >= max_results:
                            break
                
                if len(results) >= max_results:
                    break
        
        return results
    except Exception as e:
        print(f"Memory search error: {e}")
        return []

def log_message(message):
    try:
        os.makedirs("logs", exist_ok=True)
        with open("logs/debug_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().isoformat()}] {message.author.name}: {message.content}\n")
    except Exception as e:
        print(f"Logging error: {e}")

def clear_short_term_memory(keep_last_n=5):
    """
    Completely clears short-term memory except for the last N messages in each channel
    """
    try:
        # Load short-term memory
        with open("memory/short_term.json", "r") as f:
            short_term = json.load(f)
        
        # Create a new memory object with only recent messages
        new_memory = {}
        
        for channel_id, messages in short_term.items():
            # Sort messages by timestamp
            try:
                sorted_msgs = sorted(
                    messages, 
                    key=lambda x: datetime.fromisoformat(x.get("timestamp", "2000-01-01T00:00:00")),
                    reverse=True
                )
                # Keep only the most recent N messages
                new_memory[channel_id] = sorted_msgs[:keep_last_n]
            except Exception as e:
                print(f"Error sorting messages for channel {channel_id}: {e}")
                # Fallback: just keep the last N messages as they appear
                new_memory[channel_id] = messages[-keep_last_n:] if len(messages) > keep_last_n else messages
        
        # Save the trimmed memory
        with open("memory/short_term.json", "w") as f:
            json.dump(new_memory, f, indent=2)
            
        print(f"[{datetime.now().isoformat()}] Short-term memory cleared, keeping last {keep_last_n} messages per channel")
        return True
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Failed to clear short-term memory: {e}")
        return False

def force_memory_conversion():
    """
    Forces an immediate conversion of short-term to long-term memory
    Ignoring the usual time threshold
    """
    try:
        deduplicate_short_term_memory()
        convert_to_long_term_memory()
        clear_short_term_memory(keep_last_n=4)  # Keep only last 4 messages
        
        global last_memory_conversion
        last_memory_conversion = datetime.now()
        
        return True
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Forced memory conversion error: {e}")
        return False

def get_memory_stats():
    """
    Returns statistics about memory usage
    """
    stats = {
        "short_term": {
            "channels": 0,
            "total_messages": 0,
            "oldest_message": None,
            "newest_message": None,
            "message_counts_by_channel": {}
        },
        "long_term": {
            "channels": 0,
            "memories": 0,
            "users": 0,
            "diary_entries": 0
        }
    }
    
    try:
        # Short-term stats
        with open("memory/short_term.json", "r") as f:
            short_term = json.load(f)
            
        stats["short_term"]["channels"] = len(short_term)
        oldest_time = datetime.now()
        newest_time = datetime(2000, 1, 1)
        
        for channel_id, messages in short_term.items():
            message_count = len(messages)
            stats["short_term"]["total_messages"] += message_count
            stats["short_term"]["message_counts_by_channel"][channel_id] = message_count
            
            for msg in messages:
                try:
                    msg_time = datetime.fromisoformat(msg["timestamp"])
                    if msg_time < oldest_time:
                        oldest_time = msg_time
                    if msg_time > newest_time:
                        newest_time = msg_time
                except:
                    pass
        
        if oldest_time < datetime.now():
            stats["short_term"]["oldest_message"] = oldest_time.isoformat()
        if newest_time > datetime(2000, 1, 1):
            stats["short_term"]["newest_message"] = newest_time.isoformat()
            
        # Long-term stats
        try:
            with open("memory/long_term.json", "r") as f:
                long_term = json.load(f)
                
            # Count channels (excluding special keys)
            channel_count = 0
            memory_count = 0
            
            for key, value in long_term.items():
                if key == "user_info":
                    stats["long_term"]["users"] = len(value)
                elif key == "diary":
                    stats["long_term"]["diary_entries"] = len(value)
                else:
                    channel_count += 1
                    memory_count += len(value)
            
            stats["long_term"]["channels"] = channel_count
            stats["long_term"]["memories"] = memory_count
        except:
            pass
            
        # Diary stats
        try:
            with open("memory/diary.json", "r") as f:
                diary = json.load(f)
                
            stats["long_term"]["diary_entries"] = len(diary)
        except:
            pass
            
    except Exception as e:
        print(f"Error getting memory stats: {e}")
        
    return stats

