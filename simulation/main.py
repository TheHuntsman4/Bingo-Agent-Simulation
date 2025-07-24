import os
import hydra
from omegaconf import DictConfig
from utils.log_memory import log_conversation, generate_conversation_id

from core.agent_manager import AgentManager
from core.bingo_manager import BingoManager
from core.conversation_manager import ConversationManager
from environments.environment_factory import EnvironmentFactory

@hydra.main(version_base=None, config_path="configs", config_name="config")
def main(cfg: DictConfig) -> None:
    """Main entry point for the simulation"""
    # Get the original working directory (project root)
    orig_cwd = hydra.utils.get_original_cwd()
    
    # Update paths to be absolute
    for key in ['outputs_dir', 'agents_dir', 'bingo_board_dir', 'bingo_output_dir']:
        cfg.paths[key] = os.path.join(orig_cwd, cfg.paths[key])
    cfg.paths.bingo_master_file = os.path.join(orig_cwd, cfg.paths.bingo_master_file)

    # Create output directories
    os.makedirs(cfg.paths.outputs_dir, exist_ok=True)
    os.makedirs(cfg.paths.bingo_output_dir, exist_ok=True)

    # Initialize managers
    agent_manager = AgentManager(cfg)
    bingo_manager = BingoManager(cfg)
    
    # Create environment
    environment = EnvironmentFactory.create_environment(cfg.environment.type, cfg, agent_manager)
    
    # Initialize conversation manager with environment
    conversation_manager = ConversationManager(cfg, agent_manager, bingo_manager, environment)

    # Run simulation
    conversation_id = generate_conversation_id()
    log_path = os.path.join(cfg.paths.outputs_dir, f"conversation_{conversation_id}.json")

    all_conversations = conversation_manager.simulate_conversations()
    log_conversation(conversation_id, all_conversations, log_path)
    
    print(f"\n📚 All conversation summaries saved to: {log_path}")

if __name__ == "__main__":
    main()
