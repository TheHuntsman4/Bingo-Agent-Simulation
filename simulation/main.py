import os
import time
import uuid
import random
from itertools import combinations
from utils.agent_base import AgentBase
from utils.log_memory import log_conversation, generate_conversation_id, digest_conversation
from utils.bingo_loader import load_and_split_bingo_boards

import os

BASE_DIR = os.path.dirname(__file__)

AGENTS_DIR = os.path.join(BASE_DIR, "agents_personas")
OUTPUTS_DIR = os.path.join(BASE_DIR, "outputs")
BINGO_BOARD_DIR = os.path.join(BASE_DIR, "bingo_boards")
BINGO_OUTPUT_DIR = os.path.join(BASE_DIR, "bingo_outputs")

CONVERSATION_ID = generate_conversation_id()
LOG_PATH = os.path.join(OUTPUTS_DIR, f"conversation_{CONVERSATION_ID}.json")
BINGO_MASTER_FILE = os.path.join(BINGO_BOARD_DIR, "alumni-simple-boards.json")

# Create output directories if needed
os.makedirs(OUTPUTS_DIR, exist_ok=True)
os.makedirs(BINGO_OUTPUT_DIR, exist_ok=True)

# Load agent personalities
agent_files = [f for f in os.listdir(AGENTS_DIR) if f.endswith(".txt")]
agent_personalities = {}
for fname in agent_files:
    with open(os.path.join(AGENTS_DIR, fname), "r") as f:
        agent_personalities[fname[:-4]] = f.read().strip()

# Create agents
agents = {}
for name, personality in agent_personalities.items():
    agent = AgentBase()
    agents[name] = {"agent": agent, "personality": personality}

# Conversation prompt template with output size limit
PROMPT_TEMPLATE = (
    "You are {name}. Here is your background: {personality}\n"
    "You are in a conversation with {other_name}.\n"
    "Your task: respond naturally, in character, and keep the conversation going.\n"
    "IMPORTANT: Keep your response concise (maximum 1-2 sentences).\n"
    "If you wish to end your turn, append <END OF EXCHANGE> to your message.\n"
    "If you wish to end the conversation, append <END OF CONVERSATION> to your message.\n"
    "Do not end the conversation unless you feel it is natural to do so.\n"
    "Here is a summary of the conversation so far:\n{conversation_summary}\n"
    "Your response:"
)


def safe_get_response(agent, prompt, max_retries=3, delay=5):
    """Safely get response with rate limiting and retry logic"""
    for attempt in range(max_retries):
        try:
            response = agent.get_response(prompt)
            # Add delay to respect rate limits
            time.sleep(delay)
            return response
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                print(f"Rate limit hit, waiting {delay * (attempt + 1)} seconds...")
                time.sleep(delay * (attempt + 1))
            else:
                print(f"Error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    raise
    return None


def safe_digest_conversation(prev_digest, history, max_retries=3, delay=1):
    """Safely digest conversation with retry logic"""
    for attempt in range(max_retries):
        try:
            digest = digest_conversation(prev_digest, history)
            time.sleep(delay)
            return digest.content if hasattr(digest, 'content') else str(digest)
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                print(f"Rate limit hit during digestion, waiting {delay * (attempt + 1)} seconds...")
                time.sleep(delay * (attempt + 1))
            else:
                print(f"Error digesting conversation on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    # Return a fallback summary if digestion fails
                    return f"Conversation summary: {len(history)} exchanges have occurred."
    return "Conversation summary: Unable to generate digest."


# def simulate_conversation(agents, max_turns=10):
#     agent_names = list(agents.keys())
#     history = []
#     turn = 0
#     ended = False
    
#     # Initialize conversation digest for each agent
#     conversation_digest = "No conversation has occurred yet."

#     print(f"Starting conversation between: {', '.join(agent_names)}")

#     while turn < max_turns and not ended:
#         turn_responses = {}
#         for idx, name in enumerate(agent_names):
#             other_name = agent_names[1 - idx]
#             agent = agents[name]["agent"]
#             personality = agents[name]["personality"]

#             print(f"\nTurn {turn + 1}: {name} is responding...")

#             prompt = PROMPT_TEMPLATE.format(
#                 name=name,
#                 personality=personality,
#                 other_name=other_name,
#                 conversation_summary=conversation_digest,
#             )

#             try:
#                 response = safe_get_response(agent, prompt)
#                 if response:
#                     turn_responses[name] = response
#                     print(f"{name}: {response}")

#                     update_agent_bingo(name, response, matched_agent=other_name)

#                     if "<END OF CONVERSATION>" in response:
#                         ended = True
#                         print(f"{name} ended the conversation.")
#                         # Break out of the for-loop so the other agent does not respond this turn
#                         break

#                 else:
#                     print(f"Failed to get response from {name}")
#                     ended = True
#                     break

#             except Exception as e:
#                 print(f"Error getting response from {name}: {e}")
#                 ended = True
#                 break

#         if turn_responses:
#             history.append(turn_responses)
            
#             # Update conversation digest after each turn
#             try:
#                 # Convert the turn responses to a readable format for digestion
#                 turn_summary = []
#                 for agent_name, response in turn_responses.items():
#                     turn_summary.append(f"{agent_name}: {response}")
#                 turn_text = "\n".join(turn_summary)
                
#                 conversation_digest = safe_digest_conversation(conversation_digest, turn_text)
#                 print(f"Updated conversation digest: {conversation_digest}")
#             except Exception as e:
#                 print(f"Warning: Failed to update conversation digest: {e}")
                
#         turn += 1

#     print(f"\nConversation ended after {turn} turns.")
#     return history

def simulate_conversations(agents, max_total_conversations=10, turns_per_convo=5):
    agent_names = list(agents.keys())
    unique_pairs = list(combinations(agent_names, 2))
    random.shuffle(unique_pairs)

    conversation_count = 0
    all_histories = []

    print(f"Total possible unique conversations: {len(unique_pairs)}")

    for agent1, agent2 in unique_pairs:
        if conversation_count >= max_total_conversations:
            break

        print(f"\n=== Conversation {conversation_count + 1}: {agent1} ↔ {agent2} ===")

        history = simulate_single_conversation(agents, agent1, agent2, turns_per_convo)

        # Save each pair's conversation to its own JSON file
        pair_id = f"{agent1}_{agent2}_{generate_conversation_id()[:8]}"
        pair_log_path = os.path.join(OUTPUTS_DIR, f"conversation_{pair_id}.json")
        log_conversation(pair_id, history, pair_log_path)
        print(f"📝 Conversation between {agent1} and {agent2} saved to: {pair_log_path}")

        all_histories.append({
            "pair": (agent1, agent2),
            "dialogue": history
        })
        conversation_count += 1

    print(f"\n✅ All conversations complete. Total: {conversation_count}")
    return all_histories



def simulate_single_conversation(agents, name1, name2, max_turns=5):
    history = []
    ended = False
    conversation_digest = "No conversation has occurred yet."

    for turn in range(max_turns):
        turn_responses = {}

        for speaker, listener in [(name1, name2), (name2, name1)]:
            agent = agents[speaker]["agent"]
            personality = agents[speaker]["personality"]

            prompt = PROMPT_TEMPLATE.format(
                name=speaker,
                personality=personality,
                other_name=listener,
                conversation_summary=conversation_digest,
            )

            try:
                response = safe_get_response(agent, prompt)
                if response:
                    print(f"{speaker}: {response}")
                    turn_responses[speaker] = response

                    update_agent_bingo(speaker, response, matched_agent=listener)

                    if "<END OF CONVERSATION>" in response:
                        ended = True
                        print(f"{speaker} ended the conversation.")
                        break
                else:
                    ended = True
                    break
            except Exception as e:
                print(f"Error during {speaker}'s turn: {e}")
                ended = True
                break

        if turn_responses:
            history.append(turn_responses)

            # Update digest
            try:
                turn_text = "\n".join([f"{k}: {v}" for k, v in turn_responses.items()])
                conversation_digest = safe_digest_conversation(conversation_digest, turn_text)
            except Exception as e:
                print(f"Failed to update digest: {e}")

        if ended:
            break

    return history



def keyword_match(clue, response):
    clue_keywords = re.findall(r"\b\w+\b", clue)
    return any(word in response for word in clue_keywords if len(word) > 3)


def update_agent_bingo(agent_name, response, matched_agent):
    path = os.path.join(BINGO_OUTPUT_DIR, f"{agent_name}_bingo.json")
    if not os.path.exists(path):
        return

    with open(path, "r") as f:
        board = json.load(f)

    updated = False
    for row in board["squares"]:
        for square in row:
            if not square.get("filled", False):
                clue = square.get("text", "").lower()
                if keyword_match(clue, response.lower()):
                    square["filled"] = True
                    square["matched_with"] = matched_agent
                    square["response_snippet"] = response
                    updated = True

    if updated:
        with open(path, "w") as f:
            json.dump(board, f, indent=2)



if __name__ == "__main__":
    all_conversations = simulate_conversations(agents, max_total_conversations=10, turns_per_convo=5)
    log_conversation(CONVERSATION_ID, all_conversations, LOG_PATH)
    print(f"\n📚 All conversation summaries saved to: {LOG_PATH}")
