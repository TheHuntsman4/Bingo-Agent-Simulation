from typing import List, Dict, Any

class ConversationStateManager:
    """Manages conversation State Transition and udpates"""

    def __init__(self,environment):
        self.env = environment

    def start_new_conversation(self, agent1: str, agent2: str):
        """Start a new conversation between two agents"""
        self.env.agent_states[agent1].state = "conversing"
        self.env.agent_states[agent1].current_partner = agent2
        self.env.agent_states[agent1].messages_in_current_conversation = 0
        self.env.agent_states[agent1].messages_this_time_step = 0
        
        self.env.agent_states[agent2].state = "conversing"
        self.env.agent_states[agent2].current_partner = agent1
        self.env.agent_states[agent2].messages_in_current_conversation = 0
        self.env.agent_states[agent2].messages_this_time_step = 0
        
        # Load any existing conversation from short-term memory
        agent1_memory = self.env.memory_manager.get_short_term_memory(agent1)
        if agent1_memory["current_conversation"]["partner"] == agent2:
            messages_exchanged = len(agent1_memory["current_conversation"]["exchanges"])
            self.env.agent_states[agent1].messages_in_current_conversation = messages_exchanged
            self.env.agent_states[agent2].messages_in_current_conversation = messages_exchanged
        
        from .statistics_reporter import StatisticsReporter
        reporter = StatisticsReporter(self.env)
        reporter.print_conversation_status(agent1, agent2)
    
    def resume_conversation(self, agent1: str, agent2: str):
        """Resume a suspended conversation between two agents"""
        self.env.agent_states[agent1].state = "conversing"
        self.env.agent_states[agent1].current_partner = agent2
        
        # Load conversation history from short-term memory
        agent1_memory = self.env.memory_manager.get_short_term_memory(agent1)
        if agent1_memory and agent1_memory["current_conversation"]["partner"] == agent2:
            self.env.agent_states[agent1].current_conversation_history = agent1_memory["current_conversation"]["exchanges"]
        
        self.env.agent_states[agent2].state = "conversing"
        self.env.agent_states[agent2].current_partner = agent1
        
        # Load conversation history for agent2
        agent2_memory = self.env.memory_manager.get_short_term_memory(agent2)
        if agent2_memory and agent2_memory["current_conversation"]["partner"] == agent1:
            self.env.agent_states[agent2].current_conversation_history = agent2_memory["current_conversation"]["exchanges"]
        
        print(f"\nResuming conversation between {agent1} and {agent2}")
        print(f"Messages exchanged so far: {self.env.agent_states[agent1].messages_in_current_conversation}")
    
    def update_agent_states(self, agent1: str, agent2: str, ended: bool = False):
        """Update states after a conversation round or end"""
        # Update message counts
        self.env.agent_states[agent1].messages_in_current_conversation += 1
        self.env.agent_states[agent2].messages_in_current_conversation += 1
        self.env.agent_states[agent1].messages_this_time_step += 1
        self.env.agent_states[agent2].messages_this_time_step += 1

        # If conversation ended naturally
        if ended:
            # Mark conversation as complete
            self.env.agent_states[agent1].past_partners.add(agent2)
            self.env.agent_states[agent2].past_partners.add(agent1)
            
            # Increment total conversations counter
            self.env.agent_states[agent1].total_conversations += 1
            self.env.agent_states[agent2].total_conversations += 1
            
            # Reset states to idle only when conversation truly ends
            self.reset_agent_state(agent1)
            self.reset_agent_state(agent2)
            
            print(f"\n🏁 Conversation completed between {agent1} and {agent2}")
        else:
            # If we've hit the messages per time step limit but conversation isn't over
            if (self.env.agent_states[agent1].messages_this_time_step >= 
                self.env.cfg.environment.settings.time_dependent.messages_per_time_step):
                print(f"\n⏸️  Time step limit reached for {agent1} and {agent2}, continuing next time step")

        # Check if this was the last possible conversation
        if self.env.all_conversations_complete():
            self.env.experiment_complete = True
    
    def reset_agent_state(self, agent_name: str):
        """Reset an agent's state to idle"""
        self.env.agent_states[agent_name].state = "idle"
        self.env.agent_states[agent_name].current_partner = None
        self.env.agent_states[agent_name].messages_in_current_conversation = 0
        self.env.agent_states[agent_name].messages_this_time_step = 0
    
    def save_conversation_state(self, agent1: str, agent2: str, ended: bool):
        """Save conversation state to memory"""
        # Get conversation history from both agents
        history1 = self.env.agent_states[agent1].current_conversation_history
        history2 = self.env.agent_states[agent2].current_conversation_history
        
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
                "messages_exchanged": self.env.agent_states[agent1].messages_in_current_conversation,
                "exchanges": combined_history
            }
            self.env.memory_manager.update_short_term_memory(agent1, agent2, exchange_data)
            
            exchange_data = {
                "partner": agent1,
                "messages_exchanged": self.env.agent_states[agent2].messages_in_current_conversation,
                "exchanges": combined_history
            }
            self.env.memory_manager.update_short_term_memory(agent2, agent1, exchange_data)
    
    def get_conversation_history(self, agent1: str, agent2: str) -> List[Dict[str, Any]]:
        """Get the current conversation history for a pair of agents"""
        history1 = self.env.agent_states[agent1].current_conversation_history
        history2 = self.env.agent_states[agent2].current_conversation_history
        return history1 + history2
