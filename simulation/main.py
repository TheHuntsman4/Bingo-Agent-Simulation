import os
import time
import uuid
from utils.agent_base import AgentBase
from utils.log_memory import log_conversation, generate_conversation_id

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
    "Here is the conversation so far:\n{history}\n"  # TODO: come up with a method to make this more concise, the more time it runs the larger the cost on the API
    "Your response:"
)


def safe_get_response(agent, prompt, max_retries=3, delay=2):
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


def simulate_conversation(agents, max_turns=20):
    agent_names = list(agents.keys())
    history = []
    turn = 0
    ended = False  # Only one agent needs to end the conversation
    current = 0

    print(f"Starting conversation between: {', '.join(agent_names)}")

    while turn < max_turns and not ended:
        turn_responses = {}
        for idx, name in enumerate(agent_names):
            other_name = agent_names[1 - idx]
            agent = agents[name]["agent"]
            personality = agents[name]["personality"]

            print(f"\nTurn {turn + 1}: {name} is responding...")

            # For history, flatten previous turn dicts into a list of strings for prompt context
            flat_history = []
            for h in history[-10:] if len(history) > 10 else history:
                if isinstance(h, dict):
                    for k, v in h.items():
                        flat_history.append(f"{k}: {v}")
                else:
                    flat_history.append(str(h))

            prompt = PROMPT_TEMPLATE.format(
                name=name,
                personality=personality,
                other_name=other_name,
                history="\n".join(flat_history),
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
        turn += 1

    print(f"\nConversation ended after {turn} turns.")
    return history


if __name__ == "__main__":
    conversation = simulate_conversation(agents)
    conversation_id = generate_conversation_id()
    log_conversation(conversation_id, conversation, LOG_PATH)
    print(f"Conversation complete. Log saved to:", "{LOG_PATH}")
