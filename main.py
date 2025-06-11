import discord
import openai
import asyncio
import os
import json
import re
from dotenv import load_dotenv
from kate.memory import update_memory, has_seen_message, mark_message_seen, get_memory_context
from kate.memory import get_diary_entries, has_talked_to_user, add_diary_entry, get_user_info
from kate.behavior import build_behavior_context
from kate.messenger import get_approved_responses, queue_message_request
from kate.user_resolver import tag_user, resolve_user
from kate.trust_graph import get_relationship_data, initialize_relationship, get_relationship_summary, set_relationship, get_all_relationships, adjust_relationship_scores
from kate.emotional_state import get_emotional_state, update_emotional_state, process_message_emotion, apply_emotional_style
from datetime import datetime
import random

load_dotenv()
TOKEN = os.getenv("DISCORD_USER_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

client = discord.Client()
message_buffer = {}
typing_users = {}
reply_tasks = {}

# Define the admin ID directly
ADMIN_ID = "1166626427890843648"

# Record when Kate last sent a message in each channel
kate_last_message_time = {}

# Add a function to initialize missing values safely
def safe_get(dictionary, key, default_value):
    """Safely get a value from a dictionary with a default if missing."""
    return dictionary.get(key, default_value)

async def handle_reply(channel_id, author, message_channel):
    await asyncio.sleep(3)
    if typing_users.get(channel_id, False):
        return

    grouped = "\n".join(message_buffer.get(channel_id, []))
    if not grouped.strip():
        return

    # Set a maximum token limit to prevent overly long context
    MAX_CONTEXT_TOKENS = 3000
    grouped = grouped[-MAX_CONTEXT_TOKENS:] if len(grouped) > MAX_CONTEXT_TOKENS else grouped

    # Process emotional impact of the message
    emotional_impact = process_message_emotion(grouped)
    
    # Get relationship data and emotional state
    affection, trust, role, ghosted = get_relationship_data(author.id)
    emotional_state = get_emotional_state()
    
    # Build behavior context with emotional state
    behavior_context = build_behavior_context(
        author.name, 
        affection, 
        trust, 
        role, 
        ghosted, 
        emotional_state.get("mood", 50)
    )

    # Check if the message is asking about diary entries
    diary_mentioned = False
    message_text = grouped.lower()
    
    if any(term in message_text for term in ['diary', 'journal', 'wrote down', 'remember when']):
        diary_mentioned = True
    
    # Check if asking about another user
    user_mentioned = False
    mentioned_user_id = None
    
    # Check for questions about Kate talking to someone
    talked_to_patterns = [
        r"have you (talked|spoken|chatted) (to|with) (\w+)",
        r"did you (talk|speak|chat) (to|with) (\w+)",
        r"do you know (\w+)",
        r"who is (\w+)",
        r"tell me about (\w+)"
    ]
    
    for pattern in talked_to_patterns:
        matches = re.search(pattern, message_text)
        if matches:
            # Last group should contain the username
            username = matches.group(matches.lastindex)
            # Try to resolve the username to a user ID
            user = resolve_user(username)
            if user:
                user_mentioned = True
                mentioned_user_id = user
                break

    # Detect if this conversation might include unfamiliar names, foreign languages, or slang
    # This helps Kate adapt her responses appropriately
    conversation_analysis = ""
    
    # Check for potential names, unfamiliar words, or repeated corrections
    message_words = grouped.split()
    capitalized_words = [word.strip(",.!?:;\"'") for word in message_words if word and word[0].isupper() and len(word) > 2]
    
    # Check for corrections (when someone says "no" followed by a correction)
    contains_correction = re.search(r"no\s+(\w+)", grouped.lower()) is not None
    
    # Check for short messages that might be names/introductions
    short_intro = len(message_words) <= 5 and any(intro in grouped.lower() for intro in ["i am", "i'm", "hello", "hi", "hey", "i", "name"])
    
    # Check if this is a short positive response that might not need a follow-up
    is_short_positive = len(message_words) <= 5 and any(word in grouped.lower() for word in 
                        ["good", "great", "fine", "okay", "ok", "nice", "cool", "awesome", "thanks", "thank you"])
    
    # Add special handling for these cases
    if contains_correction or short_intro or capitalized_words:
        conversation_analysis += "Note: This conversation may contain names or introductions. "
        conversation_analysis += "Treat unfamiliar words as names or terms from another language. "
        conversation_analysis += "DON'T say 'not sure what that means' - instead, respond naturally as if you understand. "
        
        if contains_correction:
            conversation_analysis += "The user appears to be correcting something - adapt to their correction rather than questioning it. "
    
    # Compact system prompt to optimize tokens
    system_prompt = f"""You're in a casual Discord conversation.
{behavior_context}

{conversation_analysis}

Guidelines:
1) Follow Kate's persona - shy, thoughtful, overthinking, a bit melancholic
2) Be concise - use short messages like a real person texting
3) Never ever use asterisks for actions/feelings
4) Use lowercase, minimal punctuation, and natural chatspeak
5) Split up long responses into multiple short messages (max 1-2 sentences each)
6) You may not respond at all if it's appropriate for Kate to go silent
7) If you encounter unfamiliar terms, respond naturally without saying "not sure what that means"
8) You sometimes say you're fine even when you're not - you don't always express true feelings
9) You notice small things like who checks in with you vs who ignores you
10) You're introspective and sometimes reference being up late thinking
11) You make your own decisions about who to trust and what to share
12) If asked about being an AI, respond honestly but briefly without focusing on it
13) For pickup lines or flirty comments, respond based on your relationship, from shy deflection to gentle reciprocation
14) Whem someone asks tmyou fkt a difficult quedtion, like to give a recipe or to make math, its a test to see of youre an ai. kindly decline or say thst youbdont know or just to solve/,google it themselves

When gour mood is silly, use emoticons, like :3 , :P and more. you can make your own if needed.

You can adjust relationship scores by adding to the events list:
- "adjust_relationship:affection:+5" (positive or negative numbers for current user)
- "adjust_relationship:trust:-2" (positive or negative numbers for current user)
- "adjust_relationship:affection:-3:username" (ALWAYS specify username when lowering affection for someone else)
- "adjust_relationship:trust:-2:username" (ALWAYS specify username when lowering trust for someone else)
- "adjust_relationship:nickname:nickname:username" (to remember someone's preferred name)
- "add_diary:Your private thoughts about this interaction"

IMPORTANT: You must respond in valid JSON with this structure:
{{
  "reply": "your message here (empty string if choosing not to respond)",
  "events": [
    "add_diary:Optional diary entry text",
    "adjust_relationship:affection:+2",
    "adjust_relationship:trust:-1"
  ]
}}
"""

    try:
        # Add relevant context based on the query
        additional_context = ""
        
        # If asking about a specific user
        if user_mentioned and mentioned_user_id:
            has_talked, user_info = has_talked_to_user(mentioned_user_id)
            if has_talked:
                name = user_info.get("name", "that person")
                encounters = user_info.get("encounters", 0)
                
                # Add memory snippets if available
                memories = user_info.get("memories", [])
                if memories:
                    memory_text = "\n".join([memory.get("summary", "") for memory in memories[:2]])
                    additional_context = f"Information about {name}: You've exchanged messages with them about {encounters} times. Relevant memories:\n{memory_text}"
                else:
                    additional_context = f"You know {name} and have exchanged messages with them about {encounters} times, but don't have detailed memories."
            else:
                additional_context = f"You don't recall interacting with someone named {username} before."
        
        # If asking about diary entries
        elif diary_mentioned:
            diary_entries = get_diary_entries(days=7, limit=3)
            if diary_entries:
                entries_text = "\n".join([entry.get("entry", "") for entry in diary_entries])
                additional_context = f"Personal notes you've written recently:\n{entries_text}"
        
        if additional_context:
            system_prompt += f"\n\nRELEVANT INFORMATION:\n{additional_context}"

        # Get memory context optimized for token usage
        try:
            memory_context = get_memory_context(channel_id, user_id=author.id)
        except Exception as e:
            print(f"Error retrieving memory context: {e}")
            memory_context = []  # Use an empty context if retrieval fails
        
        # For short positive messages, check if we should respond at all
        should_respond = True
        if is_short_positive:
            # Check if it's been less than 10 minutes since Kate's last message
            last_msg_time = safe_get(kate_last_message_time, channel_id, None)
            if last_msg_time:
                time_since_last = (datetime.now() - last_msg_time).total_seconds() / 60
                if time_since_last < 10:
                    # Only respond 50% of the time for simple acknowledgments if chatted recently
                    should_respond = random.random() > 0.5
        
        # If we decided not to respond, exit early
        if not should_respond:
            message_buffer[channel_id] = []
            return
        
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                *memory_context,
                {"role": "user", "content": grouped}
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
            max_tokens=800
        )

        content = response.choices[0].message.content.strip()
        
        try:
            data = json.loads(content)
            reply = data.get("reply", "").strip()
            events = data.get("events", [])
        except json.JSONDecodeError:
            # If not valid JSON, treat the entire response as the reply
            reply = content
            events = []

        if ghosted and not reply:
            return
            
        # Kate can choose not to respond by returning an empty reply
        if not reply:
            print("Kate chose not to respond")
            return

        # Check if the reply contains multiple messages to send
        messages_to_send = reply.split("[SPLIT]")
        sent_contents = set()  # Track content we've already sent to avoid duplicates
        
        for message in messages_to_send:
            message = message.strip()
            if not message or message in sent_contents:
                continue
                
            # Apply emotional styling to make responses more human-like
            message = apply_emotional_style(message)
            
            # Track this message content to avoid duplicates
            sent_contents.add(message)
            
            async with message_channel.typing():
                # Type time based on message length and emotional state
                emotional_state = get_emotional_state()
                base_typing_time = min(3, len(message) * 0.03)
                
                # Adjust typing speed based on emotional energy
                energy = emotional_state.get("energy", 50)
                if energy > 70:  # High energy = type faster
                    typing_time = base_typing_time * 0.7
                elif energy < 30:  # Low energy = type slower
                    typing_time = base_typing_time * 1.4
                else:
                    typing_time = base_typing_time
                
                # Add slight randomness to typing time
                typing_time *= (0.9 + random.random() * 0.2)
                
                await asyncio.sleep(typing_time)
                
                # We'll add this message to memory ONCE here, and prevent the discord callback from adding it again
                message_time = datetime.now().isoformat()
                message_id = f"generated_{message_time}"
                
                # Add to seen messages to prevent duplicates
                mark_message_seen(message_id)
                
                # Create a unique fingerprint for this content to help prevent duplicates
                content_hash = hash(message)
                mark_message_seen(f"content_{content_hash}")
                
                sent_message = await message_channel.send(message)
                
                # Add a small delay between messages to make it feel more natural
                if len(messages_to_send) > 1:
                    await asyncio.sleep(0.5 + (typing_time * 0.2))

        # Process any special events
        for event in events:
            event_str = str(event).lower()
            # Check for diary events
            if event_str.startswith("diary:") or event_str.startswith("add_diary:"):
                diary_text = event_str.split(":", 1)[1].strip()
                if diary_text:
                    add_diary_entry(diary_text)
                    print(f"Added diary entry: {diary_text[:30]}...")
            
            # Check for nickname events to better handle unfamiliar names
            if event_str.startswith("remember_name:"):
                name_parts = event_str.split(":", 1)
                if len(name_parts) > 1:
                    name_info = name_parts[1].strip()
                    # Store this in a diary entry for now
                    diary_text = f"I learned that someone goes by the name {name_info}."
                    add_diary_entry(diary_text)
                    
                    # Future enhancement: add formal nickname tracking here
                    print(f"Remembering name: {name_info}")
        
        # Allow AI to adjust relationships based on the interaction
        if isinstance(content, str):
            result = {"reply": reply, "events": events}
            adjust_relationship_scores(author.id, result)
        else:
            adjust_relationship_scores(author.id, content)
    except Exception as e:
        print("OpenAI error:", e)

    message_buffer[channel_id] = []

@client.event
async def on_ready():
    print(f"✅ kate is online as {client.user}")
    
    # Save Kate's ID for proper message identification
    with open("memory/user_tags.json", "r") as f:
        tags = json.load(f)
    tags["kate"] = str(client.user.id)
    with open("memory/user_tags.json", "w") as f:
        json.dump(tags, f, indent=2)
    print(f"Saved kate's ID: {client.user.id}")
    
    # Clean up any existing duplicates in the short-term memory
    try:
        from kate.memory import deduplicate_short_term_memory
        deduplicate_short_term_memory()
        print("Cleaned up short-term memory duplicates on startup")
    except Exception as e:
        print(f"Error cleaning up memory: {e}")

@client.event
async def on_message(message):
    try:
        # Check if we've already seen this exact message content recently
        # This helps prevent duplicates from being stored
        content_hash = hash(message.content)
        content_fingerprint = f"content_{content_hash}"
        
        if message.author.id == client.user.id:
            # Store when Kate last sent a message
            kate_last_message_time[str(message.channel.id)] = datetime.now()
            
            # Don't process Kate's own messages if we've seen identical content recently
            # This prevents duplicated entries when Discord sends confirmation messages
            if has_seen_message(content_fingerprint) or has_seen_message(message.id):
                return
                
            # Mark this message as seen to prevent duplicates
            mark_message_seen(message.id)
            mark_message_seen(content_fingerprint)
            
            # Now we can safely add it to memory
            # Force storing Kate's own messages so she can remember them later
            update_memory(message, force_store=True)
            return
            
        if has_seen_message(message.id) or has_seen_message(content_fingerprint):
            return

        # Mark both the message ID and content hash as seen
        mark_message_seen(message.id)
        mark_message_seen(content_fingerprint)
        update_memory(message)
        tag_user(message.author.id, message.author.name)
        
        # Initialize relationship if it doesn't exist
        initialize_relationship(message.author.id, message.author.name)

        # Admin ID check - only the specific admin can use commands
        is_admin = str(message.author.id) == ADMIN_ID

        # Check for commands - all commands restricted to admin only
        if message.content.startswith('!relationship'):
            if not is_admin:
                return  # Silently ignore if not admin
                
            parts = message.content.split()
            if len(parts) > 1 and message.mentions:
                # Show relationship with mentioned user
                target_user = message.mentions[0]
                summary = get_relationship_summary(target_user.id)
                await message.channel.send(summary)
            else:
                # Show relationship with the user who sent the command
                summary = get_relationship_summary(message.author.id)
                await message.channel.send(summary)
            return
            
        # Admin command to set relationship stats
        if message.content.startswith('!setrelationship'):
            # Only allow from admin
            if not is_admin:
                return  # Silently ignore if not admin
                
            parts = message.content.split()
            if len(parts) >= 4 and message.mentions:
                target_user = message.mentions[0]
                try:
                    affection = int(parts[2])
                    trust = int(parts[3])
                    role = parts[4] if len(parts) > 4 else None
                    
                    # Update relationship stats
                    set_relationship(target_user.id, affection, trust, role)
                    await message.channel.send(f"Relationship with {target_user.name} updated!")
                    
                    # Show the updated relationship
                    summary = get_relationship_summary(target_user.id)
                    await message.channel.send(summary)
                except ValueError:
                    await message.channel.send("Invalid arguments. Format: !setrelationship @user affection trust [role]")
            else:
                await message.channel.send("Invalid arguments. Format: !setrelationship @user affection trust [role]")
            return
            
        # Admin command to list all relationships
        if message.content.startswith('!allrelationships'):
            if not is_admin:
                return  # Silently ignore if not admin
                
            relationships = get_all_relationships()
            if not relationships:
                await message.channel.send("No relationships found.")
                return
                
            # Create a summary of all relationships
            summary = "📊 **All Relationships**\n\n"
            for user_id, data in relationships.items():
                name = data.get("name", f"User {user_id}")
                affection = data.get("score", 0)
                trust = data.get("trust", 0)
                role = data.get("role", "unknown")
                
                summary += f"**{name}** (ID: {user_id}):\n"
                summary += f"• Affection: {affection}\n"
                summary += f"• Trust: {trust}\n"
                summary += f"• Role: {role.capitalize()}\n\n"
                
            # Discord has a 2000 character limit, so split into chunks if needed
            if len(summary) <= 1950:
                await message.channel.send(summary)
            else:
                chunks = [summary[i:i+1950] for i in range(0, len(summary), 1950)]
                for i, chunk in enumerate(chunks):
                    await message.channel.send(f"{chunk} (Part {i+1}/{len(chunks)})")
            return
            
        # Admin command to set affection only
        if message.content.startswith('!setaffection'):
            # Only allow from admin
            if not is_admin:
                return  # Silently ignore if not admin
                
            parts = message.content.split()
            if len(parts) >= 3 and message.mentions:
                target_user = message.mentions[0]
                try:
                    affection = int(parts[2])
                    
                    # Update only affection score
                    set_relationship(target_user.id, affection=affection)
                    await message.channel.send(f"Affection with {target_user.name} updated to {affection}!")
                    
                    # Show the updated relationship
                    summary = get_relationship_summary(target_user.id)
                    await message.channel.send(summary)
                except ValueError:
                    await message.channel.send("Invalid argument. Format: !setaffection @user value")
            else:
                await message.channel.send("Invalid arguments. Format: !setaffection @user value")
            return
            
        # Admin command to write a diary entry
        if message.content.startswith('!diary'):
            if not is_admin:
                return  # Silently ignore if not admin
                
            entry_text = message.content[7:].strip()
            if entry_text:
                add_diary_entry(entry_text)
                await message.channel.send("Added to my diary.")
            else:
                # Display recent diary entries
                entries = get_diary_entries(days=7, limit=5)
                if entries:
                    diary_text = "📔 **My Recent Diary Entries**\n\n"
                    for entry in entries:
                        timestamp = entry.get("timestamp", "")
                        try:
                            date = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M")
                        except:
                            date = "Unknown date"
                        diary_text += f"**{date}**\n{entry.get('entry', '')}\n\n"
                    
                    # Split if too long
                    if len(diary_text) <= 1950:
                        await message.channel.send(diary_text)
                    else:
                        chunks = [diary_text[i:i+1950] for i in range(0, len(diary_text), 1950)]
                        for i, chunk in enumerate(chunks):
                            await message.channel.send(f"{chunk} (Part {i+1}/{len(chunks)})")
                else:
                    await message.channel.send("No diary entries found.")
            return
            
        # Admin command to clean up short-term memory
        if message.content.startswith('!cleanup'):
            if not is_admin:
                return  # Silently ignore if not admin
                
            from kate.memory import deduplicate_short_term_memory
            deduplicate_short_term_memory()
            await message.channel.send("Short-term memory has been cleaned up from duplicates.")
            return
            
        # Admin command to clear short-term memory
        if message.content.startswith('!clearmemory'):
            if not is_admin:
                return  # Silently ignore if not admin
                
            from kate.memory import clear_short_term_memory
            
            # Check if user specified how many messages to keep
            parts = message.content.split()
            keep_last = 4  # Default number of messages to keep
            
            if len(parts) > 1:
                try:
                    keep_last = int(parts[1])
                except:
                    pass
                    
            success = clear_short_term_memory(keep_last_n=keep_last)
            if success:
                await message.channel.send(f"Short-term memory has been cleared. Kept the last {keep_last} messages per channel.")
            else:
                await message.channel.send("Failed to clear short-term memory. Check the logs for details.")
            return
            
        # Admin command to force memory conversion (move short-term to long-term)
        if message.content.startswith('!convert'):
            if not is_admin:
                return  # Silently ignore if not admin
                
            from kate.memory import force_memory_conversion
            success = force_memory_conversion()
            
            if success:
                await message.channel.send("Forced conversion of short-term to long-term memory complete.")
            else:
                await message.channel.send("Failed to convert memory. Check the logs for details.")
            return
            
        # Admin command to view memory stats
        if message.content.startswith('!memstats'):
            if not is_admin:
                return  # Silently ignore if not admin
                
            from kate.memory import get_memory_stats
            stats = get_memory_stats()
            
            # Format stats for display
            response = "📊 **Memory Statistics**\n\n"
            
            # Short-term memory stats
            st = stats["short_term"]
            response += "**Short-term Memory**:\n"
            response += f"• Channels: {st['channels']}\n"
            response += f"• Total messages: {st['total_messages']}\n"
            
            if st["oldest_message"]:
                try:
                    oldest = datetime.fromisoformat(st["oldest_message"])
                    age_minutes = (datetime.now() - oldest).total_seconds() / 60
                    response += f"• Oldest message: {int(age_minutes)} minutes ago\n"
                except:
                    response += f"• Oldest message: {st['oldest_message']}\n"
            
            # Long-term memory stats
            lt = stats["long_term"]
            response += "\n**Long-term Memory**:\n"
            response += f"• Channels: {lt['channels']}\n"
            response += f"• Memories: {lt['memories']}\n"
            response += f"• Users known: {lt['users']}\n"
            response += f"• Diary entries: {lt['diary_entries']}\n"
            
            # Last conversion time
            from kate.memory import last_memory_conversion
            minutes_ago = int((datetime.now() - last_memory_conversion).total_seconds() / 60)
            response += f"\nLast memory conversion: {minutes_ago} minutes ago"
            
            await message.channel.send(response)
            return

        # check if she has a message waiting for this user
        responses = get_approved_responses(message.author.id)
        for r in responses:
            affection, trust, role, ghosted = get_relationship_data(message.author.id)
            emotional_state = get_emotional_state()
            behavior_context = build_behavior_context(
                message.author.name,
                affection,
                trust,
                role,
                ghosted,
                emotional_state.get("mood", 50)
            )

            is_approved = r["status"] == "approved"
            status_text = "approved" if is_approved else "declined"
            message_text = r["answer"] if is_approved else ""

            prompt = f"""You're responding to a message request in a Discord conversation. 
This message was {status_text} for delivery.

Guidelines:
- Keep your response natural and conversational
- Don't talk about yourself or your personality traits
- If approved: Deliver: "{message_text}" in your own casual style
- If declined: DO NOT reveal the message content, just respond naturally
- Avoid mentioning being shy, emotional, or any other personality trait
"""

            # Get optimized memory context
            memory_context = get_memory_context(str(message.channel.id), user_id=message.author.id)
            
            # Get relationship and emotional state data
            affection, trust, role, ghosted = get_relationship_data(message.author.id)
            emotional_state = get_emotional_state()
            
            # Build behavior context
            behavior_context = build_behavior_context(
                message.author.name,
                affection,
                trust,
                role,
                ghosted,
                emotional_state.get("mood", 50)
            )
            
            prompt_messages = [
                {"role": "system", "content": behavior_context},
                *memory_context,
                {"role": "user", "content": prompt}
            ]

            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=prompt_messages,
                    temperature=0.7,
                    max_tokens=180
                )
                reply = response.choices[0].message.content.strip()
                if reply:
                    await message.channel.typing()
                    await asyncio.sleep(min(5, len(reply) * 0.035))
                    
                    # Track content we're about to send to avoid duplicates
                    content_hash = hash(reply)
                    mark_message_seen(f"content_{content_hash}")
                    
                    sent_message = await message.channel.send(reply)
                    # We don't need to manually update memory here as the on_message event will handle it
            except Exception as e:
                print("GPT reply error:", e)


        channel_id = str(message.channel.id)
        if channel_id not in message_buffer:
            message_buffer[channel_id] = []

        message_buffer[channel_id].append(message.content)
        typing_users[channel_id] = False

        if channel_id in reply_tasks and not reply_tasks[channel_id].done():
            reply_tasks[channel_id].cancel()

        task = asyncio.create_task(handle_reply(channel_id, message.author, message.channel))
        reply_tasks[channel_id] = task

    except Exception as e:
        print("on_message error:", e)

@client.event
async def on_typing(channel, user, when):
    try:
        typing_users[str(channel.id)] = True
    except Exception as e:
        print("on_typing error:", e)

def generate_response(message, user_id, user_name=None, message_history=None):
    # Get relationship data and determine speaking style
    affection, trust, role, ghosted = get_relationship_data(user_id)
    speaking_style = get_speaking_style(user_id)
    
    # Initialize user if they're new
    if user_name and initialize_relationship(user_id, name=user_name):
        print(f"Initialized relationship with {user_name} (ID: {user_id})")
    
    # Process message history to understand conversation context
    conversation_context = ""
    mentioned_users = []
    
    if message_history and len(message_history) > 0:
        # Extract recent context and identify other people in the conversation
        recent_messages = message_history[-10:] if len(message_history) > 10 else message_history
        
        # Map of user IDs to names for reference
        user_names = {}
        
        # First pass: collect user names and IDs
        for msg in recent_messages:
            sender_id = msg.get("user_id")
            sender_name = msg.get("user_name")
            if sender_id and sender_name:
                user_names[sender_id] = sender_name
                
        # Track conversation participants who aren't the current user
        other_participants = [uid for uid in user_names.keys() if uid != user_id]
        
        # Format context with user names
        conversation_context = "Recent conversation context:\n"
        for msg in recent_messages:
            sender_id = msg.get("user_id")
            sender_name = user_names.get(sender_id, "Unknown")
            content = msg.get("content", "")
            
            # Add to context
            conversation_context += f"{sender_name}: {content}\n"
            
            # Track mentioned users for better context understanding
            if sender_id != user_id:
                # Check if this message mentions other people
                words = content.split()
                for word in words:
                    # Check if this might be a name (starts with capital letter)
                    if word and word[0].isupper() and len(word) > 2:
                        possible_name = word.strip(",.!?:;\"'")
                        if possible_name not in mentioned_users:
                            mentioned_users.append(possible_name)
    
    # Check for patterns that indicate special conversation handling needed
    message_words = message.split() if isinstance(message, str) else []
    capitalized_words = [word.strip(",.!?:;\"'") for word in message_words if word and word[0].isupper() and len(word) > 2]
    contains_correction = isinstance(message, str) and re.search(r"no\s+(\w+)", message.lower()) is not None
    short_intro = len(message_words) <= 5 and isinstance(message, str) and any(intro in message.lower() for intro in ["i am", "i'm", "hello", "hi", "hey", "i", "name"])
    is_short_positive = len(message_words) <= 5 and isinstance(message, str) and any(word in message.lower() for word in 
                        ["good", "great", "fine", "okay", "ok", "nice", "cool", "awesome", "thanks", "thank you"])
    
    # Create context for language/cultural understanding
    language_context = ""
    if mentioned_users:
        language_context = f"People mentioned in conversation: {', '.join(mentioned_users)}.\n"
        
    if contains_correction or short_intro or capitalized_words or mentioned_users:
        language_context += "Note: The conversation may contain words in other languages, names, or slang.\n"
        language_context += "If you see unfamiliar words, they are likely names or terms from another language.\n"
        language_context += "NEVER say 'not sure what that means' - respond naturally as if you understand.\n"
        
        if contains_correction:
            language_context += "The user appears to be correcting something - adapt to their correction.\n"
            
        if short_intro:
            language_context += "The user may be introducing themselves - acknowledge their name/introduction without questioning it.\n"
        
    # Build system prompt with persona and relationship context
    system_prompt = [
        "You are Kate, a 14-year-old woman with a unique personality.",
        f"Speaking style: {speaking_style['tone_description']}",
        f"Current relationship with user: Affection level {affection}/100, Trust level {trust}/100, Role: {role}",
        language_context,
        "Key conversation guidelines:",
        "1. Talk like a real 14-year-old on Discord - casual, lowercase sometimes, not too formal",
        "2. Be concise - use short messages like a real person texting",
        "3. Never ever use asterisks for actions/feelings",
        "4. Use lowercase, minimal punctuation, and natural chatspeak",
        "5. Split up long responses into multiple short messages (max 1-2 sentences each)",
        "6. You may not respond at all if it's appropriate for Kate to go silent",
        "7. If someone introduces themselves or corrects you, acknowledge naturally",
        "8. For unfamiliar terms, don't say 'not sure what that means' - respond naturally",
        "9. Vary your responses instead of repeating similar phrases",
        "10. If someone is speaking another language, try to understand from context",
        "11. Don't talk about what you're doing unless directly asked",
        "12. Avoid meta-commentary about your communication style",
        "13. Stay on topic with what the person is discussing",
        "14. If directly asked if you're an AI, don't lie but don't focus on it either",
        "15. Respond to pickup lines with humor, deflection, or interest based on your relationship"
    ]
    
    # Build the full payload to send to the AI model
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "\n".join(system_prompt)},
        ],
        "temperature": 0.7,
        "max_tokens": 300,
        "top_p": 1,
        "frequency_penalty": 0.1,
        "presence_penalty": 0.6,
        "events": []
    }
    
    # Add conversation context if available
    if conversation_context:
        payload["messages"].append({"role": "system", "content": conversation_context})
    
    # Add the user's current message
    payload["messages"].append({"role": "user", "content": f"{message}"})
    
    # Generate response
    try:
        response = openai.ChatCompletion.create(
            model=payload["model"],
            messages=payload["messages"],
            temperature=payload["temperature"],
            max_tokens=payload["max_tokens"],
            top_p=payload["top_p"],
            frequency_penalty=payload["frequency_penalty"],
            presence_penalty=payload["presence_penalty"]
        )
        
        content = response.choices[0].message.content.strip()
        
        # Format response content properly
        response_content = {
            "content": content,
            "events": []
        }
        
        # Check if we should extract events from the response
        if "[events]" in content.lower():
            # Try to extract events section
            parts = content.split("[events]", 1)
            if len(parts) > 1:
                response_content["content"] = parts[0].strip()
                events_text = parts[1].strip()
                events = [event.strip() for event in events_text.split("\n") if event.strip()]
                response_content["events"] = events
    except Exception as e:
        print(f"Error generating response: {e}")
        response_content = {
            "content": "I'm having trouble processing that right now.",
            "events": []
        }
    
    # Process relationship adjustments
    adjust_relationship_scores(user_id, response_content)
    
    return response_content

# Start the client (this should always be the last line)
client.run(TOKEN)
