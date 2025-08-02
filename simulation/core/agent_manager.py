import os
import time
from typing import Dict, Any, Optional
from omegaconf import DictConfig
from utils.agent_base import AgentBase
import random

class AgentManager:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.agents: Dict[str, Dict[str, Any]] = {}
        self._load_agents(cfg)
        self._load_prompt_template()

    def _load_prompt_template(self) -> None:
        """Load the prompt template from file"""
        template_path = os.path.join(os.path.dirname(self.cfg.paths.base_dir), self.cfg.agent.agent.prompt_template_file)
        try:
            with open(template_path, "r") as f:
                self.prompt_template = f.read().strip()
        except Exception as e:
            print(f"Error loading prompt template: {e}")
            self.prompt_template = "You are {name}. Your personality: {personality}. You are talking to {other_name}. Previous conversation: {conversation_summary}"

    def _load_agents(self, cfg: DictConfig) -> None:
        """Load all agent personalities and initialize agents"""
        max_agents = cfg.experiment["max_agents"]
        print("Max agents: ", max_agents)
        print(f"Loading agents from {self.cfg.paths.agents_dir}")
        agent_files = [f for f in os.listdir(self.cfg.paths.agents_dir) if f.endswith(".txt")]
        print(f"Found {len(agent_files)} agent files")
        
        if max_agents < len(agent_files):
            agent_files = random.sample(agent_files, max_agents)
            print(f"Using only {max_agents} agents: {agent_files}")
        
        for fname in agent_files:
            with open(os.path.join(self.cfg.paths.agents_dir, fname), "r") as f:
                personality = f.read().strip()
                name = fname[:-4]
                self.agents[name] = {
                    "agent": AgentBase(),
                    "personality": personality
                }

    def safe_get_response(self, agent: AgentBase, prompt: str) -> Optional[str]:
        """Safely get response with rate limiting and retry logic"""
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
        """Return list of all agent names"""
        return list(self.agents.keys())

    def get_agent(self, name: str) -> Dict[str, Any]:
        """Get agent by name"""
        return self.agents.get(name) 