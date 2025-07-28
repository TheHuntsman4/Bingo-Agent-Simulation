from typing import List, Dict, Any, Tuple
import random
import json
import os
from datetime import datetime
from omegaconf import DictConfig
from core.agent_manager import AgentManager
from .base_environment import BaseEnvironment

class TestEnvironment(BaseEnvironment):
    def __init__(self, cfg: DictConfig, agent_manager: AgentManager):
        super().__init__(cfg, agent_manager)
        self.current_step = 0
        self.conversation_pairs = []
        self.completed_pairs = set()
        self.debug_mode = cfg.debug  # Use the simple debug flag
        
        # Setup debug logging if enabled
        if self.debug_mode:
            # Create logs in the Hydra output directory
            log_dir = os.path.join(os.getcwd(), "debug_logs")
            print(f"Debug logs will be saved in {log_dir}")
            os.makedirs(log_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self.log_file = open(os.path.join(log_dir, f'debug_log_{timestamp}.txt'), 'w')
            self.log_header()
        
        self.initialize_random_pairs()
        self.print_experiment_setup()

    def log_header(self):
        """Write initial header information to log file"""
        header = f"""=== Debug Log Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===
Configuration:
- Max Agents: {self.cfg.environment.settings.test.max_agents}
- Max Messages per Conversation: {self.cfg.environment.settings.test.messages_per_conversation}
- Max Time Steps: {self.cfg.environment.settings.test.max_time_steps}
"""
        self.log_file.write(header + "\n")
        self.log_file.flush()

    def print_debug(self, section: str, content: Any):
        """Print debug information to both console and file if in debug mode"""
        if not self.debug_mode:
            return
            
        # Format the debug message
        separator = f"\n{'='*20} {section} {'='*20}"
        if isinstance(content, (dict, list)):
            content_str = json.dumps(content, indent=2)
        else:
            content_str = str(content)
        message = f"{separator}\n{content_str}\n{'='*50}\n"
        
        # Print to console
        print(message)
        
        # Write to log file
        if hasattr(self, 'log_file'):
            self.log_file.write(message)
            self.log_file.flush()

    def __del__(self):
        """Cleanup: close log file if it exists"""
        if hasattr(self, 'log_file'):
            self.log_file.close()

    def initialize_random_pairs(self):
        """Initialize random pairs of agents based on max_agents setting"""
        available_agents = self.agent_manager.get_agent_names()
        max_agents = min(self.cfg.environment.settings.test.max_agents, len(available_agents))
        
        # Ensure max_agents is even to form pairs
        if max_agents % 2 != 0:
            max_agents -= 1
        
        if max_agents < 2:
            raise ValueError("Need at least 2 agents for the test environment")

        # Randomly select agents and create pairs
        selected_agents = random.sample(available_agents, max_agents)
        self.conversation_pairs = [
            (selected_agents[i], selected_agents[i + 1])
            for i in range(0, max_agents, 2)
        ]
        
        if self.debug_mode:
            self.print_debug("SELECTED PAIRS", {
                f"Pair {i+1}": f"{agent1} ↔ {agent2}"
                for i, (agent1, agent2) in enumerate(self.conversation_pairs)
            })

    def print_experiment_setup(self):
        """Print initial experiment setup information"""
        setup_info = {
            "Maximum Agents": self.cfg.environment.settings.test.max_agents,
            "Number of Pairs": len(self.conversation_pairs),
            "Max Messages per Conversation": self.cfg.environment.settings.test.messages_per_conversation,
            "Debug Mode": self.debug_mode
        }
        self.print_debug("EXPERIMENT SETUP", setup_info)

    def get_conversation_pairs(self) -> List[tuple]:
        """Get all active conversation pairs"""
        active_pairs = [pair for pair in self.conversation_pairs if pair not in self.completed_pairs]
        if self.debug_mode:
            self.print_debug("ACTIVE PAIRS", {
                "Total Pairs": len(self.conversation_pairs),
                "Active Pairs": [f"{agent1} ↔ {agent2}" for agent1, agent2 in active_pairs],
                "Completed Pairs": [f"{agent1} ↔ {agent2}" for agent1, agent2 in self.completed_pairs]
            })
        return active_pairs

    def should_continue_conversation(self, history: List[Dict[str, str]]) -> bool:
        """Check if the current pair should continue conversing"""
        if not history:
            return True

        # Get the last exchange
        last_turn = history[-1]
        agent_pair = tuple(last_turn.keys())
        
        if self.debug_mode:
            self.print_debug("CONVERSATION STATE", {
                "Pair": f"{agent_pair[0]} ↔ {agent_pair[1]}",
                "Messages Exchanged": len(history),
                "Last Exchange": last_turn
            })
        
        # If this pair is already marked as complete, don't continue
        if agent_pair in self.completed_pairs:
            return False
        
        # Check if message limit reached
        if len(history) >= self.cfg.environment.settings.test.messages_per_conversation:
            self.print_debug("CONVERSATION ENDED", f"Reached maximum messages for pair {agent_pair[0]} ↔ {agent_pair[1]}")
            self.completed_pairs.add(agent_pair)
            return False

        # Check if anyone ended the conversation
        for response in last_turn.values():
            if "<END OF CONVERSATION>" in response:
                self.print_debug("CONVERSATION ENDED", f"Ended by agent for pair {agent_pair[0]} ↔ {agent_pair[1]}")
                self.completed_pairs.add(agent_pair)
                return False

        return True

    def get_conversation_context(self, agent1: str, agent2: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """Get conversation context including time step and message counts"""
        pair = (agent1, agent2)
        is_complete = pair in self.completed_pairs
        total_pairs = len(self.conversation_pairs)
        completed_pairs = len(self.completed_pairs)
        
        context = {
            # Test environment specific parameters
            "time_step": self.current_step,
            "messages_exchanged": len(history) if history else 0,
            "max_messages": self.cfg.environment.settings.test.messages_per_conversation,
            "conversation_complete": is_complete,
            
            # Default values for compatibility with other environments
            "max_time_steps": 1,  # Only one time step needed for test
            "total_possible_conversations": total_pairs,
            "completed_conversations": completed_pairs,
            "past_partners_agent1": [],  # No past partners tracking in test
            "past_partners_agent2": [],
            "total_conversations_agent1": 0,
            "total_conversations_agent2": 0,
            "available_partners_agent1": 0,  # No partner tracking in test
            "available_partners_agent2": 0,
            "experiment_complete": completed_pairs >= total_pairs
        }
        
        if self.debug_mode:
            self.print_debug("CONVERSATION CONTEXT", {
                "Pair": f"{agent1} ↔ {agent2}",
                "Context": context,
                "History Length": len(history) if history else 0
            })
        
        return context 