from abc import ABC, abstractmethod
from typing import List, Dict, Any
from omegaconf import DictConfig
from core.agent_manager import AgentManager

class BaseEnvironment(ABC):
    def __init__(self, cfg: DictConfig, agent_manager: AgentManager):
        self.cfg = cfg
        self.agent_manager = agent_manager

    @abstractmethod
    def get_conversation_pairs(self) -> List[tuple]:
        """Return list of agent pairs that should converse"""
        pass

    @abstractmethod
    def should_continue_conversation(self, history: List[Dict[str, str]]) -> bool:
        """Determine if a conversation should continue"""
        pass

    @abstractmethod
    def get_conversation_context(self, agent1: str, agent2: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Get any additional context needed for the conversation"""
        pass 