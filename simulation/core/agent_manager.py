import os
import time
from typing import Dict, Any, Optional
from omegaconf import DictConfig
from utils.agent_base import AgentBase
import random
import yaml  # Add YAML support

class AgentManager:
    # manages all AI agents in the simulation
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.agents: Dict[str, Dict[str, Any]] = {}
        self._load_agents(cfg)
        self._load_prompt_template()

    def _load_prompt_template(self) -> None:
        # loads the template used for formatting prompts to agents
        template_path = os.path.join(os.path.dirname(self.cfg.paths.base_dir), self.cfg.agent.agent.prompt_template_file)
        try:
            with open(template_path, "r") as f:
                self.prompt_template = f.read().strip()
        except Exception as e:
            print(f"Error loading prompt template: {e}")
            self.prompt_template = "You are {name}. Your personality: {personality}. You are talking to {other_name}. Previous conversation: {conversation_summary}"

    def _load_agents(self, cfg: DictConfig) -> None:
        # loads agent personalities from YAML or TXT files and creates agent instances
        max_agents = cfg.experiment["max_agents"]
        print("Max agents: ", max_agents)
        print(f"Loading agents from {self.cfg.paths.agents_dir}")
        
        # Get both YAML and TXT files
        agent_files = [f for f in os.listdir(self.cfg.paths.agents_dir) 
                      if f.endswith((".yaml", ".txt"))]
        print(f"Found {len(agent_files)} agent files")
        
        if max_agents < len(agent_files):
            agent_files = random.sample(agent_files, max_agents)
            print(f"Using only {max_agents} agents: {agent_files}")
        
        for fname in agent_files:
            try:
                file_path = os.path.join(self.cfg.paths.agents_dir, fname)
                name = fname.rsplit('.', 1)[0]  # Remove extension to get name
                
                if fname.endswith('.yaml'):
                    # Load YAML file
                    with open(file_path, "r") as f:
                        persona = yaml.safe_load(f)
                        name = persona.get('ID', name)  # Use ID from YAML if available
                        # Create a dictionary of all persona fields except ID
                        personality_data = {k: v for k, v in persona.items() if k != 'ID'}
                else:
                    # Load TXT file - entire content becomes the personality
                    with open(file_path, "r") as f:
                        personality_data = f.read().strip()
                
                self.agents[name] = {
                    "agent": AgentBase(),
                    "personality": personality_data
                }
            except Exception as e:
                print(f"Error loading agent file {fname}: {e}")
                continue

    def safe_get_response(self, agent: AgentBase, prompt: str) -> Optional[str]:
        # gets response from agent with rate limiting and retries on failure
        for attempt in range(self.cfg.agent.agent.max_retries):
            try:
                response = agent.get_response(prompt)
                time.sleep(self.cfg.agent.agent.delay)
                return response
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    print(f"Rate limit hit, waiting {self.cfg.agent.agent.delay * (attempt + 1)} seconds...")
                    time.sleep(self.cfg.agent.agent.delay * (attempt + 1))
                else:
                    print(f"Error on attempt {attempt + 1}: {e}")
                    if attempt == self.cfg.agent.agent.max_retries - 1:
                        raise
        return None

    def get_agent_names(self) -> list:
        # returns list of all available agent names
        return list(self.agents.keys())

    def get_agent(self, name: str) -> Dict[str, Any]:
        # gets an agent by their name
        return self.agents.get(name) 