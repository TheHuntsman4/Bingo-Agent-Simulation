from abc import ABC, abstractmethod
import os
import json
from typing import Dict, List, Any, Optional
from omegaconf import DictConfig
from datetime import datetime
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from utils.token_counter import TokenCounter
from utils.log_memory import global_token_counter


class MemoryManager(ABC):
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg
        
        # Set up memory paths
        self.base_memory_path = os.path.join(os.path.dirname(cfg.paths.base_dir), 
                                           cfg.paths.outputs_dir, 
                                           cfg.paths.agent_memories_dir)
        self.long_term_path = os.path.join(self.base_memory_path, cfg.paths.long_term_memories)
        self.short_term_path = os.path.join(self.base_memory_path, cfg.paths.short_term_memories)
        
        # Create memory directories
        self._ensure_memory_dirs()
        
    def _ensure_memory_dirs(self) -> None:
        """Ensure memory directories exist"""
        os.makedirs(self.long_term_path, exist_ok=True)
        os.makedirs(self.short_term_path, exist_ok=True)
        
    def _get_memory_file_path(self, agent_id: str, memory_type: str) -> str:
        """Get the path to an agent's memory file"""
        if memory_type not in ["long_term", "short_term"]:
            raise ValueError("memory_type must be either 'long_term' or 'short_term'")
            
        base_path = self.long_term_path if memory_type == "long_term" else self.short_term_path
        return os.path.join(base_path, f"{agent_id}.json")
    
    def get_long_term_memory(self, agent_id: str) -> Dict[str, Any]:
        """Retrieve agent's long-term memory"""
        file_path = self._get_memory_file_path(agent_id, "long_term")
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading long-term memory file for agent {agent_id}")
        return {"agent_insights": {}}
        
    def get_short_term_memory(self, agent_id: str, partner_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve agent's short-term memory"""
        file_path = self._get_memory_file_path(agent_id, "short_term")
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading short-term memory file for agent {agent_id}")
        return {"current_conversation": {"partner": partner_id, "exchanges": []}}
    
    @abstractmethod
    def update_long_term_memory(self, agent_id: str, other_agent_id: str, conversation_summary: str) -> None:
        """Update agent's long-term memory with conversation insights"""
        pass
    
    @abstractmethod
    def update_short_term_memory(self, agent_id: str, other_agent_id: str, exchange: Dict[str, str]) -> None:
        """Update agent's short-term memory with the latest exchange"""
        pass
    
    @abstractmethod
    def clear_short_term_memory(self, agent_id: str, partner_id: Optional[str] = None) -> None:
        """Clear agent's short-term memory"""
        pass
    
    @abstractmethod
    def archive_short_term_memory(self, agent_id: str, partner_id: Optional[str] = None) -> None:
        """Archive agent's short-term memory"""
        pass
    
    def digest_conversation(self, prev_digest: str, history: str) -> str:
        """Digest a conversation using Gemma model and return a summary"""
        try:
            model = ChatGoogleGenerativeAI(
                model="gemma-3-27b-it",
                google_api_key=os.getenv("GOOGLE_API_KEY"),
                temperature=0.1,
            )
            
            prompt = PromptTemplate(
                input_variables=["prev_digest", "history"],
                template="""You are a helpful assistant.
                Here is the previous digest of the conversation: {prev_digest}
                Here is the history of the conversation: {history}
                Please digest the conversation and return a concise summary (less than 50 words).
                """
            )
            
            formatted_prompt = prompt.format(prev_digest=prev_digest, history=history)
            response = model.invoke(formatted_prompt)
            
            # Track token usage if counter is available
            if global_token_counter is not None:
                global_token_counter.add_api_call(
                    prompt=formatted_prompt,
                    response=response.content if hasattr(response, 'content') else str(response)
                )
            
            return response.content if hasattr(response, 'content') else str(response)
            
        except Exception as e:
            print(f"Error digesting conversation: {e}")
            return "Failed to generate conversation digest."