from typing import Dict, List, Any, Optional
from omegaconf import DictConfig
from abc import ABC, abstractmethod

from utils.log_memory import global_token_counter
from core.agent_manager import AgentManager
from core.bingo_manager import BingoManager
from simulation.environments.time_dependent.memory_manager import MemoryManager
from environments.base_environment import BaseEnvironment


class ConversationManager(ABC):
    def __init__(self, cfg: DictConfig, agent_manager: AgentManager, bingo_manager: BingoManager, environment: BaseEnvironment, token_counter=None):
        self.cfg = cfg
        self.agent_manager = agent_manager
        self.bingo_manager = bingo_manager
        self.environment = environment
        self.memory_manager = MemoryManager(cfg)
        self.token_counter = token_counter
        
        # Set the global token counter for log_memory.py (Remove this if this doesnt work properly)
        global global_token_counter
        
    # Simulate a single conversation between two agents    
    @abstractmethod
    def simulate_conversation(self) -> List[Dict[str, str]]:
        """Simulates a single conversation between two agents.
        Returns:
            List of conversation turns as dictionaries
        """
        pass
     
    # Simulate multiple conversations between different agents   
    @abstractmethod
    def simulate_multiple_conversations(self) -> List[Dict[str, Any]]:
        
        pass
        