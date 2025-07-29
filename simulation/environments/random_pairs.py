from itertools import combinations
import random
from typing import List, Dict, Any

from .base_environment import BaseEnvironment

class RandomPairsEnvironment(BaseEnvironment):
    def get_conversation_pairs(self) -> List[tuple]:
        """Return randomly shuffled pairs of all agents"""
        agent_names = self.agent_manager.get_agent_names()
        unique_pairs = list(combinations(agent_names, 2))
        random.shuffle(unique_pairs)
        return unique_pairs

    def should_continue_conversation(self, history: List[Dict[str, str]]) -> bool:
        """Check if conversation should continue based on max turns and end markers"""
        if not history:
            return True
            
        # Check if max turns reached
        if len(history) >= self.cfg.conversation.conversation.turns_per_conversation:
            return False
            
        # Check if any agent ended the conversation
        last_turn = history[-1]
        for response in last_turn.values():
            if "<END OF CONVERSATION>" in response:
                return False
                
        return True

    def get_conversation_context(self, agent1: str, agent2: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Get basic conversation context"""
        return {
            "max_turns": self.cfg.conversation.conversation.turns_per_conversation,
            "current_turn": len(history) if history else 0
        } 