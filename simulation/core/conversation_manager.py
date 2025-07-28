import os
import time
from typing import Dict, List, Any
from omegaconf import DictConfig

from utils.log_memory import log_conversation, generate_conversation_id, digest_conversation
from core.agent_manager import AgentManager
from core.bingo_manager import BingoManager
from environments.base_environment import BaseEnvironment

class ConversationManager:
    def __init__(self, cfg: DictConfig, agent_manager: AgentManager, bingo_manager: BingoManager, environment: BaseEnvironment):
        self.cfg = cfg
        self.agent_manager = agent_manager
        self.bingo_manager = bingo_manager
        self.environment = environment

    def safe_digest_conversation(self, prev_digest: str, history: str) -> str:
        """Safely digest conversation with retry logic"""
        for attempt in range(self.cfg.conversation.conversation.digest.max_retries):
            try:
                digest = digest_conversation(prev_digest, history)
                time.sleep(self.cfg.conversation.conversation.digest.delay)
                return digest.content if hasattr(digest, 'content') else str(digest)
            except Exception as e:
                if "429" in str(e) or "quota" in str(e).lower():
                    print(f"Rate limit hit during digestion, waiting {self.cfg.conversation.conversation.digest.delay * (attempt + 1)} seconds...")
                    time.sleep(self.cfg.conversation.conversation.digest.delay * (attempt + 1))
                else:
                    print(f"Error digesting conversation on attempt {attempt + 1}: {e}")
                    if attempt == self.cfg.conversation.conversation.digest.max_retries - 1:
                        return f"Conversation summary: {len(history)} exchanges have occurred."
        return "Conversation summary: Unable to generate digest."

    def simulate_single_conversation(self, name1: str, name2: str) -> List[Dict[str, str]]:
        """Simulate a conversation between two agents"""
        history = []
        conversation_digest = "No conversation has occurred yet."

        while self.environment.should_continue_conversation(history):
            turn_responses = {}
            context = self.environment.get_conversation_context(name1, name2, history)

            for speaker, listener in [(name1, name2), (name2, name1)]:
                agent_data = self.agent_manager.get_agent(speaker)
                if not agent_data:
                    continue

                prompt = self.agent_manager.prompt_template.format(
                    name=speaker,
                    personality=agent_data["personality"],
                    other_name=listener,
                    conversation_summary=conversation_digest,
                    **context  # Add environment-specific context
                )

                (f"Prompt that is being used now {speaker}: {prompt}\n\n")
                try:
                    response = self.agent_manager.safe_get_response(agent_data["agent"], prompt)
                    if response:
                        # print(f"{speaker}: {response}")
                        print(f"{speaker}: Response")
                        turn_responses[speaker] = response
                        self.bingo_manager.update_agent_bingo(speaker, response, matched_agent=listener)
                    else:
                        break
                except Exception as e:
                    print(f"Error during {speaker}'s turn: {e}")
                    break

            if turn_responses:
                history.append(turn_responses)
                try:
                    turn_text = "\n".join([f"{k}: {v}" for k, v in turn_responses.items()])
                    conversation_digest = self.safe_digest_conversation(conversation_digest, turn_text)
                except Exception as e:
                    print(f"Failed to update digest: {e}")

        return history

    def simulate_conversations(self) -> List[Dict[str, Any]]:
        """Simulate multiple conversations between different agent pairs"""
        conversation_pairs = self.environment.get_conversation_pairs()
        conversation_count = 0
        all_histories = []

        print(f"Total possible conversations: {len(conversation_pairs)}")

        for agent1, agent2 in conversation_pairs:
            if conversation_count >= self.cfg.conversation.conversation.max_total_conversations:
                break

            print(f"\n=== Conversation {conversation_count + 1}: {agent1} ↔ {agent2} ===")

            history = self.simulate_single_conversation(agent1, agent2)

            # Save each pair's conversation to its own JSON file
            pair_id = f"{agent1}_{agent2}_{generate_conversation_id()[:8]}"
            pair_log_path = os.path.join(self.cfg.paths.outputs_dir, f"conversation_{pair_id}.json")
            log_conversation(pair_id, history, pair_log_path)
            print(f"📝 Conversation between {agent1} and {agent2} saved to: {pair_log_path}")

            all_histories.append({
                "pair": (agent1, agent2),
                "dialogue": history
            })
            conversation_count += 1

        print(f"\n✅ All conversations complete. Total: {conversation_count}")
        return all_histories 