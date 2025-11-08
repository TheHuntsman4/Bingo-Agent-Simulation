from typing import List, Tuple, Set
import random

class ConversationPairingManager:
    """Manages the pairing logic for agents"""

    def __init__(self, environments):
        self.env = environments

    def get_idle_agents(self) -> List[str]:
        """Get list of agents that are currently idle"""
        return [name for name, state in self.env.agent_states.items() 
                if state.state == "idle"]
    
    def has_available_partners(self, agent_name: str) -> bool:
        """Check if an agent has any potential partners they haven't talked to yet"""
        agent_state = self.env.agent_states[agent_name]
        all_agents = set(self.env.agent_manager.get_agent_names())
        available = all_agents - {agent_name} - agent_state.past_partners
        return len(available) > 0
    
    def can_be_partners(self, agent1: str, agent2: str) -> bool:
        """Check if two agents can be paired (haven't talked before)"""
        return (agent2 not in self.env.agent_states[agent1].past_partners and
                agent1 not in self.env.agent_states[agent2].past_partners)
    
    def pair_idle_agents(self) -> List[Tuple[str, str]]:
        """
        Pair up idle agents who haven't completed conversations.
        Priority is given to resuming conversations from previous time steps.
        
        Returns:
            List of tuples containing paired agent names
        """
        # First check if all possible conversations are complete
        if self.env.all_conversations_complete():
            self.env.experiment_complete = True
            return []

        idle_agents = self.get_idle_agents()
        # Shuffle the idle agents list for randomized pairing
        random.shuffle(idle_agents)
        new_pairs = []

        # First try to resume conversations from previous time steps
        for i in range(len(idle_agents)):
            agent1 = idle_agents[i]
            if self.env.agent_states[agent1].state != "idle":
                continue

            # Check for ongoing conversations in short-term memory
            agent1_memory = self.env.memory_manager.get_short_term_memory(agent1)
            current_conversation = agent1_memory.get("current_conversation", {})
            potential_partner = current_conversation.get("partner")

            if (potential_partner in idle_agents[i+1:] and 
                self.env.agent_states[potential_partner].state == "idle" and
                potential_partner not in self.env.agent_states[agent1].past_partners):
                # Resume conversation
                from .state_manager import ConversationStateManager
                state_manager = ConversationStateManager(self.env)
                state_manager.start_new_conversation(agent1, potential_partner)
                new_pairs.append((agent1, potential_partner))
                break

        # Then try to create new pairs for remaining idle agents
        remaining_idle = self.get_idle_agents()
        # Shuffle again for randomized new pairings
        random.shuffle(remaining_idle)
        
        for i in range(0, len(remaining_idle) - 1):
            agent1 = remaining_idle[i]
            if self.env.agent_states[agent1].state != "idle":
                continue
                
            # Shuffle potential partners for this agent
            potential_partners = remaining_idle[i+1:]
            random.shuffle(potential_partners)
            
            for agent2 in potential_partners:
                if (self.env.agent_states[agent2].state == "idle" and 
                    agent2 not in self.env.agent_states[agent1].past_partners):
                    # Start new conversation
                    from .state_manager import ConversationStateManager
                    state_manager = ConversationStateManager(self.env)
                    state_manager.start_new_conversation(agent1, agent2)
                    new_pairs.append((agent1, agent2))
                    break

        # Check again after pairing in case this was the last set of conversations
        if not new_pairs and self.env.all_conversations_complete():
            self.env.experiment_complete = True

        return new_pairs
