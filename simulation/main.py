import os
import hydra
from omegaconf import DictConfig

# TODO: CHANGE THIS TO AN EXPERIMENT FUNCTION
from utils.log_memory import log_conversation, generate_conversation_id
from utils.token_counter import TokenCounter
import time

from core.agent_manager import AgentManager
from core.bingo_manager import BingoManager
from core.conversation_manager import ConversationManager
from environments.environment_factory import EnvironmentFactory

@hydra.main(version_base=None, config_path="configs", config_name="config")
def main(cfg: DictConfig) -> None:
    """Main entry point for the simulation"""
    # Get the original working directory (project root)
    orig_cwd = hydra.utils.get_original_cwd()
    start_time = time.time()
    # Initialize token counter
    token_counter = TokenCounter()
    
    experiment_id = generate_conversation_id()
    
    print(f"Experiment ID: {experiment_id}")
    
    cfg.experiment.experiment_id = experiment_id
    
    # Update paths to be absolute
    for key in ['outputs_dir', 'agents_dir', 'bingo_board_dir', 'bingo_output_dir']:
        cfg.paths[key] = os.path.join(orig_cwd, cfg.paths[key])
    cfg.paths.bingo_master_file = os.path.join(orig_cwd, cfg.paths.bingo_master_file)
    log_path = os.path.join(cfg.paths.outputs_dir, f"conversation_{experiment_id}.json")

    # Create output directories
    os.makedirs(cfg.paths.outputs_dir, exist_ok=True)
    os.makedirs(cfg.paths.bingo_output_dir, exist_ok=True)

    # Initialize managers
    agent_manager = AgentManager(cfg)
    bingo_manager = BingoManager(cfg)
    
    # Create environment
    environment = EnvironmentFactory.create_environment(cfg.environment.type, cfg, agent_manager)
    
    # Initialize conversation manager with environment and token counter
    conversation_manager = ConversationManager(cfg, agent_manager, bingo_manager, environment, token_counter)

    # Run simulation
    all_conversations = conversation_manager.simulate_conversations()
    log_conversation(experiment_id, all_conversations, log_path)
    
    print(f"\n📚 All conversation summaries saved to: {log_path}")
    
    end_time = time.time() 
    # Save and print token usage
    token_usage_path = token_counter.save_summary(cfg.paths.outputs_dir)
    token_counter.print_summary()
    print(f"\n💰 Token usage data saved to: {token_usage_path}")
    print(f"Time taken: {(end_time - start_time)/60} minutes")

if __name__ == "__main__":
    main()
