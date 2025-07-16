import os
import time
import uuid
from utils.agent_base import AgentBase
from utils.log_memory import log_conversation, generate_conversation_id, digest_conversation

AGENTS_DIR = os.path.join(os.path.dirname(__file__), "agents_personas")
OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")
CONVERSATION_ID = generate_conversation_id()
LOG_PATH = os.path.join(OUTPUTS_DIR, f"conversation_{CONVERSATION_ID}.json")

# Create outputs directory if it doesn't exist
os.makedirs(OUTPUTS_DIR, exist_ok=True)

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


def simulate_conversation(agents, max_turns=10):
    agent_names = list(agents.keys())
    history = []
    turn = 0
    ended = False
    
    # Initialize conversation digest for each agent
    conversation_digest = "No conversation has occurred yet."

    print(f"Starting conversation between: {', '.join(agent_names)}")

    while turn < max_turns and not ended:
        turn_responses = {}
        for idx, name in enumerate(agent_names):
            other_name = agent_names[1 - idx]
            agent = agents[name]["agent"]
            personality = agents[name]["personality"]

            print(f"\nTurn {turn + 1}: {name} is responding...")

            prompt = PROMPT_TEMPLATE.format(
                name=name,
                personality=personality,
                other_name=other_name,
                conversation_summary=conversation_digest,
            )

            try:
                response = safe_get_response(agent, prompt)
                if response:
                    turn_responses[name] = response
                    print(f"{name}: {response}")

                    if "<END OF CONVERSATION>" in response:
                        ended = True
                        print(f"{name} ended the conversation.")
                        # Break out of the for-loop so the other agent does not respond this turn
                        break

                else:
                    print(f"Failed to get response from {name}")
                    ended = True
                    break

            except Exception as e:
                print(f"Error getting response from {name}: {e}")
                ended = True
                break

        if turn_responses:
            history.append(turn_responses)
            
            # Update conversation digest after each turn
            try:
                # Convert the turn responses to a readable format for digestion
                turn_summary = []
                for agent_name, response in turn_responses.items():
                    turn_summary.append(f"{agent_name}: {response}")
                turn_text = "\n".join(turn_summary)
                
                conversation_digest = safe_digest_conversation(conversation_digest, turn_text)
                print(f"Updated conversation digest: {conversation_digest}")
            except Exception as e:
                print(f"Warning: Failed to update conversation digest: {e}")
                
        turn += 1

    print(f"\nConversation ended after {turn} turns.")
    return history


if __name__ == "__main__":
    conversation = simulate_conversation(agents)
    conversation_id = generate_conversation_id()
    log_conversation(conversation_id, conversation, LOG_PATH)
    print(f"Conversation complete. Log saved to: {LOG_PATH}")
