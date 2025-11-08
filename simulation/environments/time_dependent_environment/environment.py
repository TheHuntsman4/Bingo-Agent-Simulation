from typing import List, Dict, Tuple, Any
import random
from omegaconf import DictConfig
from core.agent_manager import AgentManager
from core.memory_manager import MemoryManager
from core.base_environment import BaseEnvironment
from .agent_state import AgentState
from .pairing_manager import ConversationPairingManager
from .state_manager import ConversationStateManager
from .statistics_reporter import StatisticsReporter

class TimeDependentEnvironment(BaseEnvironment):
    """Main Orchestrator for Time Dependent Convos"""

    def __init__(self, cfg: DictConfig, agent_manager: AgentManager):
        super().__init__(cfg, agent_manager)
        self.agent_states: Dict[str, AgentState] = {}
        self.current_step = 0
        self.experiment_complete = False
        self.memory_manager = MemoryManager(cfg) 
        self.initialize_agent_states()
        self.total_possible_conversations = self.calculate_total_possible_conversations()
    
        if hasattr(cfg.environment.settings.time_dependent, 'random_seed'):
            random.seed(cfg.environment.settings.time_dependent.random_seed)
        else:
            # Using current time as seed for true randomness
            random.seed(None)
        # Helper managers
        self._pairing_manager = ConversationPairingManager(self)
        self._state_manager = ConversationStateManager(self)
        self._reporter = StatisticsReporter(self)
        
        self._reporter.print_experiment_setup()
    
    #######################
    # Initialization Functions
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

    # Conversation Tracking Functions

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
            self._reporter.print_experiment_completion()
        return completed
    
    # Agent Query Functions (Delegate to Pairing Manager)

    def get_idle_agents(self) -> List[str]:
        """Get list of agents that are currently idle"""
        return self._pairing_manager.get_idle_agents()

    def has_available_partners(self, agent_name: str) -> bool:
        """Check if an agent has any potential partners they haven't talked to yet"""
        return self._pairing_manager.has_available_partners(agent_name)

    def can_be_partners(self, agent1: str, agent2: str) -> bool:
        """Check if two agents can be paired (haven't talked before)"""
        return self._pairing_manager.can_be_partners(agent1, agent2)

    #######################
    # Logging and Status Functions
    #######################

    def print_agent_stats(self):
        """Print detailed statistics for all agents"""
        self._reporter.print_agent_stats()
    
    # Pairing Functions

    def pair_idle_agents(self) -> List[Tuple[str, str]]:
        """
        Pair up idle agents who haven't completed conversations.
        Priority is given to resuming conversations from previous time steps.
        """
        return self._pairing_manager.pair_idle_agents()

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

    # State Management Functions

    def start_new_conversation(self, agent1: str, agent2: str):
        """Start a new conversation between two agents"""
        self._state_manager.start_new_conversation(agent1, agent2)

    def resume_conversation(self, agent1: str, agent2: str):
        """Resume a suspended conversation between two agents"""
        self._state_manager.resume_conversation(agent1, agent2)

    def update_agent_states(self, agent1: str, agent2: str, ended: bool = False):
        """Update states after a conversation round or end"""
        self._state_manager.update_agent_states(agent1, agent2, ended)

    def reset_agent_state(self, agent_name: str):
        """Reset an agent's state to idle"""
        self._state_manager.reset_agent_state(agent_name)

    def save_conversation_state(self, agent1: str, agent2: str, ended: bool):
        """Save conversation state to memory"""
        self._state_manager.save_conversation_state(agent1, agent2, ended)

    def get_conversation_history(self, agent1: str, agent2: str) -> List[Dict[str, Any]]:
        """Get the current conversation history for a pair of agents"""
        return self._state_manager.get_conversation_history(agent1, agent2)

    # Time Step Management

    def start_new_time_step(self):
        """Reset message counts for all agents at start of new time step"""
        self.current_step += 1
        for state in self.agent_states.values():
            state.reset_time_step_count()

    #######################
    # Conversation Context and Control
    #######################

    def get_conversation_context(self, agent1: str, agent2: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Get conversation context including time step, message counts, and conversation history"""
        messages_exchanged = len(history) if history else 0

        return {
            "time_step": self.current_step,
            "max_time_steps": self.cfg.environment.settings.time_dependent.max_time_steps,
            "messages_exchanged": messages_exchanged,
            "max_messages": self.cfg.environment.settings.time_dependent.messages_per_time_step,
            "messages_per_time_step": self.cfg.environment.settings.time_dependent.messages_per_time_step,
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
