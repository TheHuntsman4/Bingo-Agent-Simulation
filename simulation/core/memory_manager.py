import os
import json
from typing import Dict, List, Any
from omegaconf import DictConfig

class MemoryManager:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        self.base_memory_path = os.path.join(os.path.dirname(cfg.paths.base_dir), "agent_memories")
        self.long_term_path = os.path.join(self.base_memory_path, "long_term")
        self.short_term_path = os.path.join(self.base_memory_path, "short_term")
        self._ensure_memory_dirs()

    def _ensure_memory_dirs(self):
        """Ensure memory directories exist"""
        os.makedirs(self.long_term_path, exist_ok=True)
        os.makedirs(self.short_term_path, exist_ok=True)

    def _get_memory_file_path(self, agent_id: str, memory_type: str) -> str:
        """Get the path to an agent's memory file"""
        base_path = self.long_term_path if memory_type == "long_term" else self.short_term_path
        return os.path.join(base_path, f"{agent_id}.json")

    def update_short_term_memory(self, agent_id: str, other_agent_id: str, exchange: Dict[str, str]):
        """Update agent's short-term memory with the latest exchange"""
        file_path = self._get_memory_file_path(agent_id, "short_term")
        
        # Load existing memory or create new
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                memory = json.load(f)
        else:
            memory = {
                "current_conversation": {
                    "partner": other_agent_id,
                    "exchanges": []
                }
            }
        
        # Add new exchange
        memory["current_conversation"]["exchanges"].append(exchange)
        
        # Save updated memory
        with open(file_path, 'w') as f:
            json.dump(memory, f, indent=2)

    def update_long_term_memory(self, agent_id: str, other_agent_id: str, conversation_summary: str):
        """Update agent's long-term memory with conversation insights"""
        file_path = self._get_memory_file_path(agent_id, "long_term")
        
        # Load existing memory or create new
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                memory = json.load(f)
        else:
            memory = {"agent_insights": {}}
        
        # Update or create entry for other agent
        memory["agent_insights"][other_agent_id] = conversation_summary
        
        # Save updated memory
        with open(file_path, 'w') as f:
            json.dump(memory, f, indent=2)

    def clear_short_term_memory(self, agent_id: str):
        """Clear agent's short-term memory after conversation ends"""
        file_path = self._get_memory_file_path(agent_id, "short_term")
        if os.path.exists(file_path):
            os.remove(file_path)

    def get_long_term_memory(self, agent_id: str) -> Dict[str, Any]:
        """Retrieve agent's long-term memory"""
        file_path = self._get_memory_file_path(agent_id, "long_term")
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return {"agent_insights": {}}

    def get_short_term_memory(self, agent_id: str) -> Dict[str, Any]:
        """Retrieve agent's short-term memory"""
        file_path = self._get_memory_file_path(agent_id, "short_term")
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return {"current_conversation": {"partner": None, "exchanges": []}} 