class StatisticsReporter:
    """Handles all printing and logging functionality for the environment."""

    def __init__(self,environment):
        self.env = environment

    def print_experiment_setup(self):
        """Print initial experiment setup information"""
        total_agents = len(self.env.agent_manager.get_agent_names())
        print("\n=== Experiment Setup ===")
        print(f"Total Agents: {total_agents}")
        print(f"Total Possible Conversations: {self.env.total_possible_conversations}")
        print(f"Max Messages per Conversation: {self.env.cfg.environment.settings.time_dependent.messages_per_time_step}")
        print("=" * 30)

    def print_conversation_status(self, agent1: str, agent2: str):
        """Print status of a new conversation"""
        completed = self.env.get_total_completed_conversations()
        print(f"\nNew Conversation Started:")
        print(f"Between: {agent1} and {agent2}")
        print(f"Progress: {completed}/{self.env.total_possible_conversations} conversations completed")
        progress = (completed / self.env.total_possible_conversations) * 100
        print(f"Overall Progress: {progress:.1f}%")
        
    def print_agent_stats(self):
        """Print detailed statistics for all agents"""
        print("\n=== Agent Statistics ===")
        print("Agent | Status | Conversations | Available Partners | Messages This Step")
        print("-" * 70)
        for name, state in self.env.agent_states.items():
            available = len(set(self.env.agent_manager.get_agent_names()) - {name} - state.past_partners)
            status = "Talking" if state.state == "conversing" else "Idle"
            print(f"{name:15} | {status:7} | {len(state.past_partners):12} | {available:17} | {state.messages_this_time_step:17}")
        print("-" * 70)

    def print_experiment_completion(self):
        """Print experiment completion status and statistics"""
        print("\n=== Experiment Complete! ===")
        print(f"Total Conversations Completed: {self.env.get_total_completed_conversations()}")
        print(f"Total Time Steps: {self.env.current_step}")
        self.print_agent_stats()
        print("=" * 30 + "\n")
