from typing import Set

class AgentState:
    """Represents state of an initial Agent"""

    def __init__(self, name: str):
        self.name = name
        self.state = "idle"  # "idle", "conversing", or "suspended"
        self.current_partner = None
        self.past_partners: Set[str] = set()  
        self.messages_in_current_conversation = 0
        self.messages_this_time_step = 0  # Track messages in current time step
        self.total_conversations = 0
        self.current_conversation_history = []

    def reset_time_step_count(self):
        self.messages_this_time_step =0