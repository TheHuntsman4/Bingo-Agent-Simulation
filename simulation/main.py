import os
import hydra
from omegaconf import DictConfig

from utils.log_memory import log_conversation, generate_conversation_id
from utils.token_counter import TokenCounter
import time

from core.agent_manager import AgentManager
from core.bingo_manager import BingoManager
from simulation.environments.time_dependent.conversation_manager import ConversationManager
from environments.environment_factory import EnvironmentFactory

@hydra.main(version_base=None, config_path="configs", config_name="config")
def main(cfg: DictConfig) -> None:
    # main function that runs the bingo agent simulation
    
    # get the project root directory
    orig_cwd = hydra.utils.get_original_cwd()
    start_time = time.time()
    
    # track token usage throughout the simulation
    token_counter = TokenCounter()
    
    # create unique ID for this experiment
    experiment_id = generate_conversation_id()
    print(f"Experiment ID: {experiment_id}")
    cfg.experiment.experiment_id = experiment_id
    
    # convert all paths to absolute paths
    for key in ['outputs_dir', 'agents_dir', 'bingo_board_dir']:
        cfg.paths[key] = os.path.join(orig_cwd, cfg.paths[key])
    
    # setup output directories for this experiment
    cfg.paths.outputs_dir = os.path.join(cfg.paths.outputs_dir, experiment_id)
    cfg.paths.bingo_output_dir = os.path.join(cfg.paths.outputs_dir, cfg.paths.bingo_output_dir)
    
    # create the output folders
    os.makedirs(cfg.paths.outputs_dir, exist_ok=True)
    os.makedirs(cfg.paths.bingo_output_dir, exist_ok=True)
    
    # copy bingo board files to the output directory
    for filename in os.listdir(cfg.paths.bingo_board_dir):
        if filename.endswith(".json"):
            source_path = os.path.join(cfg.paths.bingo_board_dir, filename)
            dest_path = os.path.join(cfg.paths.bingo_output_dir, filename)
            try:
                with open(source_path, "r") as source, open(dest_path, "w") as dest:
                    dest.write(source.read())
            except IOError as e:
                print(f"Error copying bingo board {filename}: {e}")
    
    log_path = os.path.join(cfg.paths.outputs_dir, f"conversation_{experiment_id}.json")

    # setup the core components needed for simulation
    agent_manager = AgentManager(cfg)
    bingo_manager = BingoManager(cfg)
    
    # create the simulation environment
    environment = EnvironmentFactory.create_environment(cfg.environment.type, cfg, agent_manager)
    
    # run the simulation and log results
    conversation_manager = ConversationManager(cfg, agent_manager, bingo_manager, environment, token_counter)
    all_conversations = conversation_manager.simulate_conversations()
    log_conversation(experiment_id, all_conversations, log_path)
    
    print(f"\n📚 All conversation summaries saved to: {log_path}")
    
    end_time = time.time()
    
    # save token usage stats
    token_usage_path = token_counter.save_summary(cfg.paths.outputs_dir)
    token_counter.print_summary()
    print(f"\n💰 Token usage data saved to: {token_usage_path}")
    print(f"Time taken: {(end_time - start_time)/60} minutes")

if __name__ == "__main__":
    main()
