from typing import List, Dict, Any, Set, Tuple
from omegaconf import DictConfig
from core.agent_manager import AgentManager
from core.memory_manager import MemoryManager
from .base_environment import BaseEnvironment

class AgentState:
    def __init__(self, name: str):
        self.name = name
        self.state = "idle"  # "idle", "conversing", or "suspended"
        self.current_partner = None
        self.past_partners: Set[str] = set()  # Set of agents this agent has already completed conversations with
        self.messages_in_current_conversation = 0
        self.messages_this_time_step = 0  # Track messages in current time step
        self.total_conversations = 0  # Track total number of completed conversations

    def reset_time_step_count(self):
        """Reset the message count for new time step"""
        self.messages_this_time_step = 0

class TimeDependentEnvironment(BaseEnvironment):
    def __init__(self, cfg: DictConfig, agent_manager: AgentManager):
        super().__init__(cfg, agent_manager)
        self.agent_states: Dict[str, AgentState] = {}
        self.current_step = 0
        self.experiment_complete = False  # Flag to track if all possible conversations are done
        self.memory_manager = MemoryManager(cfg)  # Initialize memory manager
        self.initialize_agent_states()
        self.total_possible_conversations = self.calculate_total_possible_conversations()
        self.print_experiment_setup()

    #######################
    # Utility Functions
    #######################

    def initialize_agent_states(self):
        """Initialize states for all agents"""
        for agent_name in self.agent_manager.get_agent_names():
            self.agent_states[agent_name] = AgentState(agent_name)

    def calculate_total_possible_conversations(self) -> int:
        """
        Calculate total number of possible unique conversations.
        For n agents, each agent talks to (n-1) others.
        Total is (n * (n-1)) / 2 since each conversation is counted once.
        """
        n = len(self.agent_manager.get_agent_names())
        return (n * (n - 1)) // 2

    def get_total_completed_conversations(self) -> int:
        """
        Get the total number of completed unique conversations.
        Each conversation is counted only once.
        """
        # Sum up all past partners and divide by 2 since each conversation
        # is counted twice (once for each participant)
        total = sum(len(state.past_partners) for state in self.agent_states.values())
        return total // 2

    def all_conversations_complete(self) -> bool:
        """
        Check if all possible unique conversations have occurred.
        Returns True if every agent has talked to every other agent exactly once.
        """
        completed = self.get_total_completed_conversations() >= self.total_possible_conversations
        if completed and not self.experiment_complete:
            self.print_experiment_completion()
        return completed

    def get_idle_agents(self) -> List[str]:
        """Get list of agents that are currently idle"""
        return [name for name, state in self.agent_states.items() 
                if state.state == "idle"]

    def has_available_partners(self, agent_name: str) -> bool:
        """Check if an agent has any potential partners they haven't talked to yet"""
        agent_state = self.agent_states[agent_name]
        all_agents = set(self.agent_manager.get_agent_names())
        available = all_agents - {agent_name} - agent_state.past_partners
        return len(available) > 0

    def can_be_partners(self, agent1: str, agent2: str) -> bool:
        """Check if two agents can be paired (haven't talked before)"""
        return (agent2 not in self.agent_states[agent1].past_partners and
                agent1 not in self.agent_states[agent2].past_partners)

    #######################
    # Logging and Status Functions
    #######################

    def print_experiment_setup(self):
        """Print initial experiment setup information"""
        total_agents = len(self.agent_manager.get_agent_names())
        print("\n=== Experiment Setup ===")
        print(f"Total Agents: {total_agents}")
        print(f"Total Possible Conversations: {self.total_possible_conversations}")
        print(f"Max Messages per Conversation: {self.cfg.environment.settings.time_dependent.messages_per_time_step}")
        print("=" * 30)

    def print_conversation_status(self, agent1: str, agent2: str):
        """Print status of a new conversation"""
        completed = self.get_total_completed_conversations()
        print(f"\nNew Conversation Started:")
        print(f"Between: {agent1} and {agent2}")
        print(f"Progress: {completed}/{self.total_possible_conversations} conversations completed")
        progress = (completed / self.total_possible_conversations) * 100
        print(f"Overall Progress: {progress:.1f}%")
        
    def print_agent_stats(self):
        """Print detailed statistics for all agents"""
        print("\n=== Agent Statistics ===")
        print("Agent | Status | Conversations | Available Partners | Messages This Step")
        print("-" * 70)
        for name, state in self.agent_states.items():
            available = len(set(self.agent_manager.get_agent_names()) - {name} - state.past_partners)
            status = "Talking" if state.state == "conversing" else "Idle"
            print(f"{name:15} | {status:7} | {len(state.past_partners):12} | {available:17} | {state.messages_this_time_step:17}")
        print("-" * 70)

    def print_experiment_completion(self):
        """Print experiment completion status and statistics"""
        print("\n=== Experiment Complete! ===")
        print(f"Total Conversations Completed: {self.get_total_completed_conversations()}")
        print(f"Total Time Steps: {self.current_step}")
        self.print_agent_stats()
        print("=" * 30 + "\n")

    #######################
    # Main Simulation Functions
    #######################

    def pair_idle_agents(self) -> List[Tuple[str, str]]:
        """
        Pair up idle agents who haven't completed conversations.
        Priority is given to resuming conversations from previous time steps.
        """
        # First check if all possible conversations are complete
        if self.all_conversations_complete():
            self.experiment_complete = True
            return []

        idle_agents = self.get_idle_agents()
        new_pairs = []

        # First try to resume conversations from previous time steps
        for i in range(len(idle_agents)):
            agent1 = idle_agents[i]
            if self.agent_states[agent1].state != "idle":
                continue

            # Check for ongoing conversations in short-term memory
            agent1_memory = self.memory_manager.get_short_term_memory(agent1)
            current_conversation = agent1_memory.get("current_conversation", {})
            potential_partner = current_conversation.get("partner")

            if (potential_partner in idle_agents[i+1:] and 
                self.agent_states[potential_partner].state == "idle" and
                potential_partner not in self.agent_states[agent1].past_partners):
                # Resume conversation
                self.start_new_conversation(agent1, potential_partner)
                new_pairs.append((agent1, potential_partner))
                break

        # Then try to create new pairs for remaining idle agents
        remaining_idle = self.get_idle_agents()
        for i in range(0, len(remaining_idle) - 1):
            agent1 = remaining_idle[i]
            if self.agent_states[agent1].state != "idle":
                continue
                
            for j in range(i + 1, len(remaining_idle)):
                agent2 = remaining_idle[j]
                if (self.agent_states[agent2].state == "idle" and 
                    agent2 not in self.agent_states[agent1].past_partners):
                    # Start new conversation
                    self.start_new_conversation(agent1, agent2)
                    new_pairs.append((agent1, agent2))
                    break

        # Check again after pairing in case this was the last set of conversations
        if not new_pairs and self.all_conversations_complete():
            self.experiment_complete = True

        return new_pairs

    def resume_conversation(self, agent1: str, agent2: str):
        """Resume a suspended conversation between two agents"""
        self.agent_states[agent1].state = "conversing"
        self.agent_states[agent1].current_partner = agent2
        self.agent_states[agent1].messages_in_current_conversation = self.agent_states[agent1].suspended_conversations[agent2]
        
        # Load conversation history from short-term memory
        agent1_memory = self.memory_manager.get_short_term_memory(agent1)
        if agent1_memory and agent1_memory["current_conversation"]["partner"] == agent2:
            self.agent_states[agent1].current_conversation_history = agent1_memory["current_conversation"]["exchanges"]
        
        self.agent_states[agent2].state = "conversing"
        self.agent_states[agent2].current_partner = agent1
        self.agent_states[agent2].messages_in_current_conversation = self.agent_states[agent2].suspended_conversations[agent1]
        
        # Load conversation history for agent2
        agent2_memory = self.memory_manager.get_short_term_memory(agent2)
        if agent2_memory and agent2_memory["current_conversation"]["partner"] == agent1:
            self.agent_states[agent2].current_conversation_history = agent2_memory["current_conversation"]["exchanges"]
        
        print(f"\nResuming conversation between {agent1} and {agent2}")
        print(f"Messages exchanged so far: {self.agent_states[agent1].messages_in_current_conversation}")

    def start_new_conversation(self, agent1: str, agent2: str):
        """Start a new conversation between two agents"""
        self.agent_states[agent1].state = "conversing"
        self.agent_states[agent1].current_partner = agent2
        self.agent_states[agent1].messages_in_current_conversation = 0
        self.agent_states[agent1].messages_this_time_step = 0
        
        self.agent_states[agent2].state = "conversing"
        self.agent_states[agent2].current_partner = agent1
        self.agent_states[agent2].messages_in_current_conversation = 0
        self.agent_states[agent2].messages_this_time_step = 0
        
        # Load any existing conversation from short-term memory
        agent1_memory = self.memory_manager.get_short_term_memory(agent1)
        if agent1_memory["current_conversation"]["partner"] == agent2:
            messages_exchanged = len(agent1_memory["current_conversation"]["exchanges"])
            self.agent_states[agent1].messages_in_current_conversation = messages_exchanged
            self.agent_states[agent2].messages_in_current_conversation = messages_exchanged
            
        self.print_conversation_status(agent1, agent2)

    def get_conversation_pairs(self) -> List[tuple]:
        """Get all current conversation pairs"""
        # If experiment is complete, return no pairs
        if self.experiment_complete:
            return []

        # First, create new pairs from idle agents
        new_pairs = self.pair_idle_agents()
        
        # Then get all active pairs (including newly created ones)
        active_pairs = []
        processed = set()

        for agent_name, state in self.agent_states.items():
            if (state.state == "conversing" and 
                state.current_partner and 
                agent_name not in processed):
                active_pairs.append((agent_name, state.current_partner))
                processed.add(agent_name)
                processed.add(state.current_partner)

        return active_pairs

    def start_new_time_step(self):
        """Reset message counts for all agents at start of new time step"""
        self.current_step += 1
        for state in self.agent_states.values():
            state.reset_time_step_count()

    def update_agent_states(self, agent1: str, agent2: str, ended: bool = False):
        """Update states after a conversation round or end"""
        # Update message counts
        self.agent_states[agent1].messages_in_current_conversation += 1
        self.agent_states[agent2].messages_in_current_conversation += 1
        self.agent_states[agent1].messages_this_time_step += 1
        self.agent_states[agent2].messages_this_time_step += 1

        # If conversation ended naturally
        if ended:
            # Mark conversation as complete
            self.agent_states[agent1].past_partners.add(agent2)
            self.agent_states[agent2].past_partners.add(agent1)
            
            # Increment total conversations counter
            self.agent_states[agent1].total_conversations += 1
            self.agent_states[agent2].total_conversations += 1
            
            # Reset states to idle only when conversation truly ends
            self.reset_agent_state(agent1)
            self.reset_agent_state(agent2)
            
            print(f"\n🏁 Conversation completed between {agent1} and {agent2}")
            # Only print stats when conversation ends
            self.print_agent_stats()
        else:
            # If we've hit the messages per time step limit but conversation isn't over
            if (self.agent_states[agent1].messages_this_time_step >= 
                self.cfg.environment.settings.time_dependent.messages_per_time_step):
                print(f"\n⏸️  Time step limit reached for {agent1} and {agent2}, continuing next time step")

        # Check if this was the last possible conversation
        if self.all_conversations_complete():
            self.experiment_complete = True
            self.print_agent_stats()  # Print final stats

    def reset_agent_state(self, agent_name: str):
        """Reset an agent's state to idle"""
        self.agent_states[agent_name].state = "idle"
        self.agent_states[agent_name].current_partner = None
        self.agent_states[agent_name].messages_in_current_conversation = 0
        self.agent_states[agent_name].messages_this_time_step = 0

    def save_conversation_state(self, agent1: str, agent2: str, ended: bool):
        """Save conversation state to memory"""
        # Get conversation history from both agents
        history1 = self.agent_states[agent1].current_conversation_history
        history2 = self.agent_states[agent2].current_conversation_history
        
        # Combine histories
        combined_history = history1 + history2
        
        if ended:
            # If conversation ended naturally, generate a meaningful summary and save to long-term memory
            # This part is now handled by ConversationManager
            pass
        else:
            # If conversation is ongoing, update short-term memory
            exchange_data = {
                "partner": agent2,
                "messages_exchanged": self.agent_states[agent1].messages_in_current_conversation,
                "exchanges": combined_history
            }
            self.memory_manager.update_short_term_memory(agent1, agent2, exchange_data)
            
            exchange_data = {
                "partner": agent1,
                "messages_exchanged": self.agent_states[agent2].messages_in_current_conversation,
                "exchanges": combined_history
            }
            self.memory_manager.update_short_term_memory(agent2, agent1, exchange_data)

    def get_conversation_history(self, agent1: str, agent2: str) -> List[Dict[str, Any]]:
        """Get the current conversation history for a pair of agents"""
        history1 = self.agent_states[agent1].current_conversation_history
        history2 = self.agent_states[agent2].current_conversation_history
        return history1 + history2

    def get_conversation_context(self, agent1: str, agent2: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Get conversation context including time step, message counts, and conversation history"""
        # Get suspended conversation status
        is_suspended = agent2 in self.agent_states[agent1].suspended_conversations
        messages_exchanged = (self.agent_states[agent1].suspended_conversations.get(agent2, 0) 
                            if is_suspended else len(history) if history else 0)

        return {
            "time_step": self.current_step,
            "max_time_steps": self.cfg.environment.settings.time_dependent.max_time_steps,
            "messages_exchanged": messages_exchanged,
            "max_messages": self.cfg.environment.settings.time_dependent.messages_per_time_step,
            "messages_per_time_step": self.cfg.environment.settings.time_dependent.messages_per_time_step,
            "is_suspended_conversation": is_suspended,
            "past_partners_agent1": list(self.agent_states[agent1].past_partners),
            "past_partners_agent2": list(self.agent_states[agent2].past_partners),
            "total_conversations_agent1": self.agent_states[agent1].total_conversations,
            "total_conversations_agent2": self.agent_states[agent2].total_conversations,
            "available_partners_agent1": len(set(self.agent_manager.get_agent_names()) - {agent1} - self.agent_states[agent1].past_partners),
            "available_partners_agent2": len(set(self.agent_manager.get_agent_names()) - {agent2} - self.agent_states[agent2].past_partners),
            "experiment_complete": self.experiment_complete,
            "total_possible_conversations": self.total_possible_conversations,
            "completed_conversations": self.get_total_completed_conversations()
        } 

    def should_continue_conversation(self, agent1: str, agent2: str) -> bool:
        """Check if a specific pair should continue conversing in current time step"""
        # If experiment is complete, no conversations should continue
        if self.experiment_complete:
            return False
            
        # Check if either agent has reached their message limit for this time step
        if (self.agent_states[agent1].messages_this_time_step >= 
                self.cfg.environment.settings.time_dependent.messages_per_time_step or
            self.agent_states[agent2].messages_this_time_step >= 
                self.cfg.environment.settings.time_dependent.messages_per_time_step):
            return False
            
        # Check short-term memory for end of conversation marker
        agent1_memory = self.memory_manager.get_short_term_memory(agent1)
        if agent1_memory and agent1_memory["current_conversation"]["partner"] == agent2:
            exchanges = agent1_memory["current_conversation"].get("exchanges", [])
            if exchanges:
                last_exchange = exchanges[-1]
                for response in last_exchange.values():
                    if "<END OF CONVERSATION>" in response:
                        return False
        
        return True

    def should_continue_pair(self, agent1: str, agent2: str) -> bool:
        """Check if a specific pair should continue conversing in current time step"""
        if self.experiment_complete:
            return False
            
        return (self.agent_states[agent1].messages_this_time_step < 
                self.cfg.environment.settings.time_dependent.messages_per_time_step and
                self.agent_states[agent2].messages_this_time_step < 
                self.cfg.environment.settings.time_dependent.messages_per_time_step) 