from typing import List, Dict, Any, Set, Tuple
from omegaconf import DictConfig
from core.agent_manager import AgentManager
from .base_environment import BaseEnvironment

class AgentState:
    def __init__(self, name: str):
        self.name = name
        self.state = "idle"  # "idle" or "conversing"
        self.current_partner = None
        self.past_partners: Set[str] = set()  # Set of agents this agent has already talked to
        self.messages_in_current_conversation = 0
        self.total_conversations = 0  # Track total number of completed conversations

class TimeDependentEnvironment(BaseEnvironment):
    def __init__(self, cfg: DictConfig, agent_manager: AgentManager):
        super().__init__(cfg, agent_manager)
        self.agent_states: Dict[str, AgentState] = {}
        self.current_step = 0
        self.experiment_complete = False  # Flag to track if all possible conversations are done
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
        print(f"Max Messages per Conversation: {self.cfg.environment.settings.time_dependent.messages_per_conversation}")
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
        print("Agent | Status | Conversations | Available Partners")
        print("-" * 50)
        for name, state in self.agent_states.items():
            available = len(set(self.agent_manager.get_agent_names()) - {name} - state.past_partners)
            status = "Talking" if state.state == "conversing" else "Idle"
            print(f"{name:15} | {status:7} | {len(state.past_partners):12} | {available:17}")
        print("-" * 50)

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
        Pair up idle agents who haven't conversed before.
        Each agent can have multiple conversations over time, but only one at a time,
        and never with the same partner twice.
        """
        # First check if all possible conversations are complete
        if self.all_conversations_complete():
            self.experiment_complete = True
            return []

        idle_agents = self.get_idle_agents()
        new_pairs = []

        for i in range(0, len(idle_agents) - 1):
            agent1 = idle_agents[i]
            if self.agent_states[agent1].state != "idle":
                continue
                
            for j in range(i + 1, len(idle_agents)):
                agent2 = idle_agents[j]
                if (self.agent_states[agent2].state == "idle" and 
                    self.can_be_partners(agent1, agent2)):
                    # Pair these agents
                    self.agent_states[agent1].state = "conversing"
                    self.agent_states[agent1].current_partner = agent2
                    self.agent_states[agent1].messages_in_current_conversation = 0
                    
                    self.agent_states[agent2].state = "conversing"
                    self.agent_states[agent2].current_partner = agent1
                    self.agent_states[agent2].messages_in_current_conversation = 0
                    
                    new_pairs.append((agent1, agent2))
                    # Print status for new conversation
                    self.print_conversation_status(agent1, agent2)
                    break

        # Check again after pairing in case this was the last set of conversations
        if not new_pairs and self.all_conversations_complete():
            self.experiment_complete = True

        return new_pairs

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

    def should_continue_conversation(self, history: List[Dict[str, str]]) -> bool:
        """Check if the current pair should continue conversing"""
        # If experiment is complete, no conversations should continue
        if self.experiment_complete:
            return False

        if not history:
            return True

        # Get the agents from the last exchange
        last_turn = history[-1]
        agents = list(last_turn.keys())
        if not agents:
            return False

        # Check if either agent has reached their message limit
        for agent in agents:
            state = self.agent_states[agent]
            if state.messages_in_current_conversation >= self.cfg.environment.settings.time_dependent.messages_per_conversation:
                return False

        # Check if anyone ended the conversation
        for response in last_turn.values():
            if "<END OF CONVERSATION>" in response:
                return False

        return True

    def update_agent_states(self, agent1: str, agent2: str, ended: bool = False):
        """Update states after a conversation round or end"""
        # Update message counts
        self.agent_states[agent1].messages_in_current_conversation += 1
        self.agent_states[agent2].messages_in_current_conversation += 1

        # If conversation ended or message limit reached, update states
        if ended or (self.agent_states[agent1].messages_in_current_conversation >= 
                    self.cfg.environment.settings.time_dependent.messages_per_conversation):
            # Record that these agents have talked
            self.agent_states[agent1].past_partners.add(agent2)
            self.agent_states[agent2].past_partners.add(agent1)
            
            # Increment total conversations counter
            self.agent_states[agent1].total_conversations += 1
            self.agent_states[agent2].total_conversations += 1
            
            # Reset states to idle
            self.agent_states[agent1].state = "idle"
            self.agent_states[agent1].current_partner = None
            self.agent_states[agent1].messages_in_current_conversation = 0
            
            self.agent_states[agent2].state = "idle"
            self.agent_states[agent2].current_partner = None
            self.agent_states[agent2].messages_in_current_conversation = 0

            # Print status after conversation ends
            print(f"\nConversation ended between {agent1} and {agent2}")
            if not self.experiment_complete:
                self.print_agent_stats()

            # Check if this was the last possible conversation
            if self.all_conversations_complete():
                self.experiment_complete = True

    def get_conversation_context(self, agent1: str, agent2: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Get conversation context including time step, message counts, and conversation history"""
        return {
            "time_step": self.current_step,
            "max_time_steps": self.cfg.environment.settings.time_dependent.max_time_steps,
            "messages_exchanged": len(history) if history else 0,
            "max_messages": self.cfg.environment.settings.time_dependent.messages_per_conversation,
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