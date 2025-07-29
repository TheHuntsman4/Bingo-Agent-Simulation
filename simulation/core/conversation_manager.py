import os
import time
from typing import Dict, List, Any
from omegaconf import DictConfig

from utils.log_memory import log_conversation, generate_conversation_id, digest_conversation, global_token_counter
from core.agent_manager import AgentManager
from core.bingo_manager import BingoManager
from core.memory_manager import MemoryManager
from environments.base_environment import BaseEnvironment

class ConversationManager:
    def __init__(self, cfg: DictConfig, agent_manager: AgentManager, bingo_manager: BingoManager, environment: BaseEnvironment, token_counter=None):
        self.cfg = cfg
        self.agent_manager = agent_manager
        self.bingo_manager = bingo_manager
        self.environment = environment
        self.memory_manager = MemoryManager(cfg)
        self.token_counter = token_counter
        
        # Set the global token counter for log_memory.py
        global global_token_counter
        global_token_counter = token_counter

    def safe_digest_conversation(self, prev_digest: str, history: str) -> str:
        """Safely digest conversation with retry logic"""
        for attempt in range(self.cfg.conversation.conversation.digest.max_retries):
            try:
                digest = digest_conversation(prev_digest, history)
                if self.token_counter:
                    self.token_counter.add_api_call(
                        prompt=f"Previous: {prev_digest}\nHistory: {history}",
                        response=digest.content if hasattr(digest, 'content') else str(digest)
                    )
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

    def generate_long_term_memory(self, agent_id: str, other_agent_id: str, full_history: List[Dict[str, str]]) -> str:
        """Generate long-term memory entry from conversation history"""
        history_text = "\n".join([f"{k}: {v}" for turn in full_history for k, v in turn.items()])
        memory_prompt = f"I just talked to {other_agent_id} and this is all that happened:\n{history_text}\n\nI need to condense this into a summary of what I learned about them, focusing on their personality, interests, and any important information they shared. Summary:"
        
        try:
            memory = digest_conversation("", memory_prompt)
            if self.token_counter:
                self.token_counter.add_api_call(
                    prompt=memory_prompt,
                    response=memory.content if hasattr(memory, 'content') else str(memory)
                )
            return memory.content if hasattr(memory, 'content') else str(memory)
        except Exception as e:
            print(f"Error generating long-term memory: {e}")
            return f"Had a conversation with {other_agent_id}. Unable to generate detailed memory due to error."

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
                    **context
                )

                try:
                    # response = self.agent_manager.safe_get_response(agent_data["agent"], prompt)
                    response = "Some response <END OF CONVERSATION>"
                    if response:
                        print(f"{speaker}: {response}")
                        turn_responses[speaker] = response
                        self.bingo_manager.update_agent_bingo(speaker, response, matched_agent=listener)
                        
                        # Update short-term memory for both agents
                        self.memory_manager.update_short_term_memory(speaker, listener, {speaker: response})
                        
                        # Track token usage
                        if self.token_counter:
                            self.token_counter.add_api_call(prompt=prompt, response=response)
                    else:
                        break
                except Exception as e:
                    print(f"Error during {speaker}'s turn: {e}")
                    break

            if turn_responses:
                history.append(turn_responses)
                try:
                    turn_text = "\n".join([f"{k}: {v}" for k, v in turn_responses.items()])
                    # conversation_digest = self.safe_digest_conversation(conversation_digest, turn_text)
                    conversation_digest = "Some digest"
                except Exception as e:
                    print(f"Failed to update digest: {e}")

        # At the end of conversation, update long-term memory and clear short-term
        for agent_id, other_agent_id in [(name1, name2), (name2, name1)]:
            # Generate and store long-term memory
            memory_summary = self.generate_long_term_memory(agent_id, other_agent_id, history)
            self.memory_manager.update_long_term_memory(agent_id, other_agent_id, memory_summary)
            # Clear short-term memory
            self.memory_manager.clear_short_term_memory(agent_id)

        return history

    def print_conversation_header(self, agent1: str, agent2: str, is_new: bool, time_step: int = None, max_steps: int = None):
        """Print a formatted conversation header"""
        border = "=" * 60
        if time_step is not None:
            print(f"\n{border}")
            print(f"Time Step: {time_step}/{max_steps}".center(60))
            print(border)
        
        status = "New Conversation" if is_new else "Resuming Conversation"
        print(f"\n{'🗣️  ' + status + ' 🗣️':^60}")
        print(f"{'Between ' + agent1 + ' and ' + agent2:^60}")
        print("-" * 60)

    def format_message(self, speaker: str, message: str) -> str:
        """Format a single message with proper indentation and structure"""
        speaker_color = "🔵" if speaker == message.split(":")[0] else "🔴"
        formatted_lines = []
        
        # Split message into lines and format each
        lines = message.split("\n")
        for i, line in enumerate(lines):
            if i == 0:  # First line with speaker
                formatted_lines.append(f"{speaker_color} {line.strip()}")
            else:  # Continuation lines
                formatted_lines.append(f"   {line.strip()}")
        
        return "\n".join(formatted_lines)

    def get_memory_context(self, agent1: str, agent2: str) -> Dict[str, str]:
        """Get memory context for a conversation pair"""
        # Get long-term memory insights
        agent1_memory = self.memory_manager.get_long_term_memory(agent1)
        agent2_memory = self.memory_manager.get_long_term_memory(agent2)
        
        agent1_insights = agent1_memory.get("agent_insights", {}).get(agent2, "")
        agent2_insights = agent2_memory.get("agent_insights", {}).get(agent1, "")

        # Get current short-term memory
        agent1_memory = self.memory_manager.get_short_term_memory(agent1)
        conversation_summary = ""
        
        # Get exchanges from short-term memory
        if agent1_memory and agent1_memory["current_conversation"]["partner"] == agent2:
            exchanges = agent1_memory["current_conversation"]["exchanges"]
            if exchanges:
                conversation_summary = "Previous exchanges:\n" + "\n".join(
                    [f"{k}: {v}" for exchange in exchanges for k, v in exchange.items()]
                )

        return {
            "conversation_summary": conversation_summary,
            "previous_insights_about_partner": agent1_insights,
            "partner_previous_insights": agent2_insights
        }

    def update_conversation_memory(self, agent1: str, agent2: str, exchange: Dict[str, str], ended: bool = False):
        """Update memory after each exchange"""
        # Update short-term memory with the new exchange
        agent1_memory = self.memory_manager.get_short_term_memory(agent1)
        agent2_memory = self.memory_manager.get_short_term_memory(agent2)
        
        # Update agent1's memory
        if agent1_memory["current_conversation"]["partner"] != agent2:
            agent1_memory["current_conversation"] = {
                "partner": agent2,
                "exchanges": []
            }
        agent1_memory["current_conversation"]["exchanges"].append(exchange)
        self.memory_manager.update_short_term_memory(agent1, agent2, agent1_memory["current_conversation"])
        
        # Update agent2's memory
        if agent2_memory["current_conversation"]["partner"] != agent1:
            agent2_memory["current_conversation"] = {
                "partner": agent1,
                "exchanges": []
            }
        agent2_memory["current_conversation"]["exchanges"].append(exchange)
        self.memory_manager.update_short_term_memory(agent2, agent1, agent2_memory["current_conversation"])

    def end_time_step(self):
        """Process all conversations at the end of a time step"""
        # Get all agents who have short-term memories
        processed_pairs = set()
        
        for agent_name in self.environment.agent_states.keys():
            memory = self.memory_manager.get_short_term_memory(agent_name)
            partner = memory["current_conversation"]["partner"]
            
            if not partner or (agent_name, partner) in processed_pairs or (partner, agent_name) in processed_pairs:
                continue
                
            # Mark this pair as processed
            processed_pairs.add((agent_name, partner))
            
            # Get the full conversation history
            exchanges = memory["current_conversation"]["exchanges"]
            if exchanges:
                # Generate a summary of the conversation so far
                conversation_text = "\n".join([
                    f"{k}: {v}" for exchange in exchanges for k, v in exchange.items()
                ])
                try:
                    summary = self.safe_digest_conversation("", conversation_text)
                    summary_text = summary.content if hasattr(summary, 'content') else str(summary)
                except Exception as e:
                    print(f"Error generating conversation summary: {e}")
                    summary_text = f"Conversation with {len(exchanges)} exchanges"
                
                # Update long-term memory for both agents
                self.memory_manager.update_long_term_memory(agent_name, partner, summary_text)
                self.memory_manager.update_long_term_memory(partner, agent_name, summary_text)
                
                # Only clear short-term memory if conversation ended
                if any("<END OF CONVERSATION>" in resp for exchange in exchanges for resp in exchange.values()):
                    self.memory_manager.clear_short_term_memory(agent_name)
                    self.memory_manager.clear_short_term_memory(partner)

    def simulate_conversations(self) -> List[Dict[str, Any]]:
        """Simulate multiple conversations between different agent pairs"""
        conversation_pairs = self.environment.get_conversation_pairs()
        conversation_count = 0
        all_histories = []

        print(f"\n{'📊 Simulation Overview 📊':^60}")
        print("=" * 60)
        print(f"Total possible conversations: {len(conversation_pairs)}")

        if self.cfg.environment.type != "time_dependent":
            for agent1, agent2 in conversation_pairs:
                if conversation_count >= self.cfg.conversation.conversation.max_total_conversations:
                    break

                self.print_conversation_header(agent1, agent2, True)
                history = self.simulate_single_conversation(agent1, agent2)

                # Save conversation
                pair_id = f"{agent1}_{agent2}_{generate_conversation_id()[:8]}"
                pair_log_path = os.path.join(self.cfg.paths.outputs_dir, f"conversation_{pair_id}.json")
                log_conversation(pair_id, history, pair_log_path)
                print(f"\n📝 Conversation saved to: {pair_log_path}")

                all_histories.append({
                    "pair": (agent1, agent2),
                    "dialogue": history
                })
                conversation_count += 1
        else:
            print("\n=== Starting Time-Dependent Environment Simulation ===")
            max_time_steps = self.cfg.environment.settings.time_dependent.max_time_steps
            
            for t in range(max_time_steps):
                self.environment.start_new_time_step()
                print(f"\n--- Time Step {t + 1}/{max_time_steps} ---")
                
                current_pairs = self.environment.get_conversation_pairs()
                
                for agent1, agent2 in current_pairs:
                    # Get memory context
                    memory = self.get_memory_context(agent1, agent2)
                    if memory["conversation_summary"]:
                        print(f"\n📜 Previous conversation context:")
                        print(memory["conversation_summary"])
                    
                    # Continue conversation while within time step limit
                    while self.environment.should_continue_conversation(agent1, agent2):
                        # Simulate one exchange
                        turn_responses = {}
                        
                        for speaker, listener in [(agent1, agent2), (agent2, agent1)]:
                            agent_data = self.agent_manager.get_agent(speaker)
                            if not agent_data:
                                continue
                            
                            # Build prompt with memory context
                            memory_context = ""
                            if memory["previous_insights_about_partner"]:
                                memory_context += f"\nWhat you know about {listener}: {memory['previous_insights_about_partner']}"
                            if memory["partner_previous_insights"]:
                                memory_context += f"\nWhat {listener} knows about you: {memory['partner_previous_insights']}"
                            if memory["conversation_summary"]:
                                memory_context += f"\n\nPrevious conversation:\n{memory['conversation_summary']}"
                            
                            prompt = self.agent_manager.prompt_template.format(
                                name=speaker,
                                personality=agent_data["personality"],
                                other_name=listener,
                                conversation_summary=memory_context,
                                time_step=t + 1,
                                max_time_steps=max_time_steps,
                                messages_exchanged=self.environment.agent_states[speaker].messages_in_current_conversation,
                                max_messages=self.cfg.environment.settings.time_dependent.messages_per_time_step,
                                past_partners_agent1=self.environment.agent_states[speaker].past_partners,
                                past_partners_agent2=self.environment.agent_states[listener].past_partners
                            )
                            
                            try:
                                response = self.agent_manager.safe_get_response(agent_data["agent"], prompt)
                                if response:
                                    formatted_response = self.format_message(speaker, f"{speaker}: {response}")
                                    print(f"\n{formatted_response}")
                                    turn_responses[speaker] = response
                                    self.bingo_manager.update_agent_bingo(speaker, response, matched_agent=listener)
                                    
                                    if self.token_counter:
                                        self.token_counter.add_api_call(prompt=prompt, response=response)
                            except Exception as e:
                                print(f"\n❌ Error during {speaker}'s turn: {e}")
                                continue
                        
                        if turn_responses:
                            # Update memory after each exchange
                            self.update_conversation_memory(agent1, agent2, turn_responses)
                            
                            # Check for conversation end
                            conversation_ended = any("<END OF CONVERSATION>" in resp for resp in turn_responses.values())
                            
                            # Update agent states
                            self.environment.update_agent_states(agent1, agent2, ended=conversation_ended)
                            
                            if conversation_ended:
                                print("\n🏁 Conversation naturally ended")
                                break
                        else:
                            break
                
                # Process all conversations at the end of the time step
                self.end_time_step()
                
                if self.environment.experiment_complete:
                    print("\n🎉 All possible conversations have been completed!")
                    break
            
            print("\n" + "=" * 60)
            print(f"{'📊 Simulation Complete 📊':^60}")
            print(f"Total conversations: {conversation_count}".center(60))
            print(f"Time steps used: {t + 1}/{max_time_steps}".center(60))
            print("=" * 60)
        
        return all_histories 