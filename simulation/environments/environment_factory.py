from omegaconf import DictConfig
from typing import Dict, Type

from .base_environment import BaseEnvironment
from .random_pairs import RandomPairsEnvironment
from core.agent_manager import AgentManager

class EnvironmentFactory:
    _environments: Dict[str, Type[BaseEnvironment]] = {
        "random_pairs": RandomPairsEnvironment
    }

    @classmethod
    def create_environment(cls, env_type: str, cfg: DictConfig, agent_manager: AgentManager) -> BaseEnvironment:
        """Create and return an environment instance based on type"""
        if env_type not in cls._environments:
            raise ValueError(f"Unknown environment type: {env_type}. Available types: {list(cls._environments.keys())}")
            
        environment_class = cls._environments[env_type]
        return environment_class(cfg, agent_manager) 