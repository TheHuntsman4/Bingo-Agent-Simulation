import os
import time
from typing import Dict, List, Any
from omegaconf import DictConfig
import re

from utils.log_memory import log_conversation, generate_conversation_id, digest_conversation, global_token_counter
from core.agent_manager import AgentManager
from core.bingo_manager import BingoManager
from core.memory_manager import MemoryManager
from environments.base_environment import BaseEnvironment

# ANSI escape codes for colors
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[0m\033[94m'
    OKCYAN = '\033[0m\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[0m\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class ConversationManager:
    def __init__(self, cfg: DictConfig, agent_manager: AgentManager, bingo_manager: BingoManager, environment: BaseEnvironment, token_counter=None):
        self.cfg = cfg
        self.agent_manager = agent_manager
        self.bingo_manager = bingo_manager
        self.environment = environment
        self.memory_manager = MemoryManager(cfg)
        self.token_counter = token_counter
        
        # Set the global token counter for log_memory.py (Remove this if this doesnt work properly)
        global global_token_counter
        global_token_counter = token_counter
        
        # Load both prompt templates
        self._load_prompt_template()

    def _load_prompt_template(self) -> None:
        # loads the template used for formatting prompts to agents
        base_dir = os.path.dirname(self.cfg.paths.base_dir)
        template_path = os.path.join(base_dir, self.cfg.agent.agent.prompt_template_file)
        txt_template_path = os.path.join(base_dir, "prompt_template_txt_personality.txt")
        
        try:
            # Load YAML template
            with open(template_path, "r") as f:
                self.yaml_prompt_template = f.read().strip()
            print(f"Loaded YAML prompt template from {template_path}")
            
            # Load TXT template
            with open(txt_template_path, "r") as f:
                self.txt_prompt_template = f.read().strip()
            print(f"Loaded TXT prompt template from {txt_template_path}")
            
            # Update agent manager's template to YAML template for backward compatibility
            if hasattr(self.agent_manager, 'prompt_template'):
                self.agent_manager.prompt_template = self.yaml_prompt_template
                
        except Exception as e:
            print(f"Error loading prompt templates: {e}")
            # Fallback templates
            self.yaml_prompt_template = "You are {name}. Your personality: {personality}. You are talking to {other_name}. Previous conversation: {conversation_summary}"
            self.txt_prompt_template = self.yaml_prompt_template
            print("Using fallback prompt templates")

    def safe_digest_conversation(self, prev_digest: str, history: str) -> str:
        """Safely digest conversation with retry logic"""
        # Check if digest or history is empty
        if not prev_digest or not history:
            return "No previous memory, Lets start talking"

        max_retries = self.cfg.conversation.conversation.digest.max_retries
        base_delay = self.cfg.conversation.conversation.digest.delay

        for attempt in range(max_retries):
            try:
                digest = digest_conversation(prev_digest, history)
                if self.token_counter:
                    self.token_counter.add_api_call(
                        prompt=f"Previous: {prev_digest}\nHistory: {history}",
                        response=digest.content if hasattr(digest, 'content') else str(digest)
                    )
                time.sleep(base_delay)
                return digest.content if hasattr(digest, 'content') else str(digest)
            except Exception as e:
                wait_time = base_delay * (2 ** attempt)
                if "429" in str(e) or "quota" in str(e).lower():
                    # Try to extract suggested wait time from error message
                    retry_after_match = re.search(r'retry_delay {\s*seconds: (\d+)\s*}', str(e))
                    if retry_after_match:
                        wait_time = int(retry_after_match.group(1))
                    
                    print(f"{bcolors.WARNING}Rate limit hit during digestion, waiting {wait_time} seconds...{bcolors.ENDC}")
                    time.sleep(wait_time)
                else:
                    print(f"{bcolors.FAIL}Error digesting conversation on attempt {attempt + 1}: {e}{bcolors.ENDC}")
                    if attempt == max_retries - 1:
                        print(f"{bcolors.FAIL}Max retries exceeded for non-rate-limit error.{bcolors.ENDC}")
                        break
                    time.sleep(wait_time)
        
        print(f"{bcolors.FAIL}Failed to generate conversation digest after all retries. Returning placeholder.{bcolors.ENDC}")
        return f"Conversation summary: {len(str(history))} characters of conversation have occurred."

    def generate_long_term_memory(self, agent_id: str, other_agent_id: str, full_history: List[Dict[str, str]]) -> str:
        """Generate long-term memory entry from conversation history"""
        if not full_history or len(full_history) == 0:
            return f"Had a brief interaction with {other_agent_id} but no substantial conversation occurred."
        
        # Filter out empty exchanges and clean the history
        cleaned_history = []
        for turn in full_history:
            if turn and isinstance(turn, dict):
                # Remove any empty or None values
                cleaned_turn = {k: v for k, v in turn.items() if v and isinstance(v, str) and v.strip()}
                if cleaned_turn:
                    cleaned_history.append(cleaned_turn)
        
        if not cleaned_history:
            return f"Had a conversation with {other_agent_id} but no meaningful content was exchanged."
        
        # Create a more structured history text
        history_lines = []
        for i, turn in enumerate(cleaned_history, 1):
            for speaker, message in turn.items():
                # Clean the message (remove bingo tags, etc.)
                clean_message = message.replace("<FILL IN BINGO>", "").replace("</FILL IN BINGO>", "")
                clean_message = clean_message.replace("<END OF CONVERSATION>", "").strip()
                if clean_message:
                    history_lines.append(f"{speaker}: {clean_message}")
        
        if not history_lines:
            return f"Had a conversation with {other_agent_id} but no meaningful content was exchanged."
        
        history_text = "\n".join(history_lines)
        
        # Create a more specific memory prompt
        memory_prompt = f"""I just had a conversation with {other_agent_id}. Here's what was discussed:

{history_text}

Based on this conversation, I need to create a concise summary of what I learned about {other_agent_id}. Focus on:
- Their personality traits and characteristics
- Their interests, hobbies, or passions
- Any important personal information they shared
- Their communication style or mannerisms
- Any memorable moments or insights

Summary:"""
        
        try:
            memory = digest_conversation("", memory_prompt)
            if self.token_counter:
                self.token_counter.add_api_call(
                    prompt=memory_prompt,
                    response=memory.content if hasattr(memory, 'content') else str(memory)
                )
            
            result = memory.content if hasattr(memory, 'content') else str(memory)
            
            # Ensure the result is not too long
            if len(result) > 500:
                result = result[:500] + "..."
            
            return result
            
        except Exception as e:
            print(f"{bcolors.FAIL}Error generating long-term memory for {agent_id} about {other_agent_id}: {e}{bcolors.ENDC}")
            # Return a basic summary based on conversation length
            return f"Had a conversation with {other_agent_id} involving {len(cleaned_history)} exchanges. Unable to generate detailed memory due to technical error."

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
                    other_name=listener,
                    conversation_summary=conversation_digest,
                    **context,
                    **agent_data["personality"]  # Unpack all personality fields from YAML
                )

                try:
                    # print(f"🗣️  {speaker} submitting prompt with ~{prompt_tokens} tokens...")
                    response = self.agent_manager.safe_get_response(agent_data["agent"], prompt)
                    if response:
                        color = bcolors.OKBLUE if speaker == name1 else bcolors.OKGREEN
                        print(self._format_message(speaker, response, color))
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
                    print(f"{bcolors.FAIL}Error during {speaker}'s turn: {e}{bcolors.ENDC}")
                    break

            if turn_responses:
                history.append(turn_responses)
                try:
                    turn_text = "\n".join([f"{k}: {v}" for k, v in turn_responses.items()])
                    conversation_digest = self.safe_digest_conversation(conversation_digest, turn_text)
                except Exception as e:
                    print(f"{bcolors.FAIL}Failed to update digest: {e}{bcolors.ENDC}")

        # At the end of conversation, update long-term memory and clear short-term
        for agent_id, other_agent_id in [(name1, name2), (name2, name1)]:
            # Generate and store long-term memory
            memory_summary = self.generate_long_term_memory(agent_id, other_agent_id, history)
            self.memory_manager.update_long_term_memory(agent_id, other_agent_id, memory_summary)
            # Clear short-term memory
            self.memory_manager.clear_short_term_memory(agent_id, other_agent_id)

        return history

    def print_conversation_header(self, agent1: str, agent2: str, is_new: bool, time_step: int = None, max_steps: int = None):
        """Print a formatted conversation header"""
        border = f"{bcolors.HEADER}{'=' * 80}{bcolors.ENDC}"
        if time_step is not None:
            print(f"\n{border}")
            print(f"{bcolors.HEADER}{f'Time Step: {time_step}/{max_steps}'.center(80)}{bcolors.ENDC}")
            print(border)

        status = "New Conversation" if is_new else "Resuming Conversation"
        print(f"\n{bcolors.OKCYAN}{'🗣️  ' + status + ' 🗣️':^88}{bcolors.ENDC}")
        print(f"{bcolors.OKCYAN}{'Between ' + agent1 + ' and ' + agent2:^88}{bcolors.ENDC}")
        print(f"{bcolors.OKCYAN}{'-' * 80}{bcolors.ENDC}")

    def _format_message(self, speaker: str, message: str, color: str) -> str:
        """Format a single message with proper indentation and structure"""
        # Add a blank line before each message for visual separation
        formatted_lines = ["\n"]
        
        # Split message and handle each line
        lines = message.split("\n")
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:  # Handle empty lines
                formatted_lines.append("")
                continue
                
            if i == 0:  # First line with speaker name
                formatted_lines.append(f"{color}{bcolors.BOLD}{speaker}:{bcolors.ENDC}{color} {line}{bcolors.ENDC}")
            else:  # Continuation lines - align with first line's content
                indent = " " * (len(speaker) + 2)  # +2 for the ": " after speaker name
                formatted_lines.append(f"{color}{indent}{line}{bcolors.ENDC}")
        
        return "\n".join(formatted_lines)

    def format_message(self, speaker: str, message: str) -> str:
        """Legacy format method - redirects to _format_message"""
        color = bcolors.OKBLUE if speaker == message.split(":")[0] else bcolors.OKGREEN
        return self._format_message(speaker, message.split(":", 1)[1].strip(), color)


    def get_memory_context(self, agent1: str, agent2: str) -> Dict[str, str]:
        """Get memory context for a conversation pair"""
        # Get long-term memory insights
        agent1_memory = self.memory_manager.get_long_term_memory(agent1)
        agent2_memory = self.memory_manager.get_long_term_memory(agent2)
        
        agent1_insights = agent1_memory.get("agent_insights", {}).get(agent2, "")
        agent2_insights = agent2_memory.get("agent_insights", {}).get(agent1, "")

        # Get current short-term memory
        agent1_memory = self.memory_manager.get_short_term_memory(agent1, agent2)
        conversation_summary = self.safe_digest_conversation(agent1_insights, agent1_memory["current_conversation"]["exchanges"])
        
        return {
            "conversation_summary": conversation_summary,
            "previous_insights_about_partner": agent1_insights,
            "partner_previous_insights": agent2_insights,
            "step_conversation_history": ""
            
        }

    def update_conversation_memory(self, agent1: str, agent2: str, exchange: Dict[str, str], ended: bool = False):
        """Update memory after each exchange"""
        self.memory_manager.update_short_term_memory(agent1, agent2, exchange)

        # Update agent2's memory  
        self.memory_manager.update_short_term_memory(agent2, agent1, exchange)

    def end_time_step(self):
        """Process all conversations at the end of a time step"""
        # Get all agents who have short-term memories
        processed_pairs = set()
        
        for agent_name in self.environment.agent_states.keys():
            memory = self.memory_manager.get_short_term_memory(agent_name)
            if not memory or "current_conversation" not in memory or not memory["current_conversation"].get("partner"):
                continue
                
            partner = memory["current_conversation"]["partner"]
            
            if not partner or (agent_name, partner) in processed_pairs or (partner, agent_name) in processed_pairs:
                continue
                
            # Mark this pair as processed
            processed_pairs.add((agent_name, partner))
            
            # Get the full conversation history
            exchanges = memory["current_conversation"].get("exchanges", [])
            if exchanges:
                # Convert exchanges to the format expected by generate_long_term_memory
                conversation_history = []
                for exchange in exchanges:
                    conversation_history.append(exchange)
                
                # Generate proper long-term memory using the sophisticated function
                try:
                    agent1_memory_summary = self.generate_long_term_memory(agent_name, partner, conversation_history)
                    agent2_memory_summary = self.generate_long_term_memory(partner, agent_name, conversation_history)
                    
                    # Update long-term memory for both agents
                    self.memory_manager.update_long_term_memory(agent_name, partner, agent1_memory_summary)
                    self.memory_manager.update_long_term_memory(partner, agent_name, agent2_memory_summary)
                    
                    print(f"{bcolors.OKGREEN}✅ Updated long-term memory for {agent_name} and {partner}{bcolors.ENDC}")
                    
                except Exception as e:
                    print(f"{bcolors.FAIL}Error generating long-term memory for {agent_name} and {partner}: {e}{bcolors.ENDC}")
                    # Fallback to simple summary
                    conversation_text = "\n".join([
                        f"{k}: {v}" for exchange in exchanges for k, v in exchange.items()
                    ])
                    try:
                        summary = self.safe_digest_conversation("", conversation_text)
                        summary_text = summary.content if hasattr(summary, 'content') else str(summary)
                    except Exception as e2:
                        print(f"{bcolors.FAIL}Error generating conversation summary: {e2}{bcolors.ENDC}")
                        summary_text = f"Conversation with {len(exchanges)} exchanges"
                    
                    # Update long-term memory for both agents with fallback
                    self.memory_manager.update_long_term_memory(agent_name, partner, summary_text)
                    self.memory_manager.update_long_term_memory(partner, agent_name, summary_text)
                
                # Only clear short-term memory if conversation ended
                if any("<END OF CONVERSATION>" in resp for exchange in exchanges for resp in exchange.values()):
                    self.memory_manager.clear_short_term_memory(agent_name, partner)
                    self.memory_manager.clear_short_term_memory(partner, agent_name)

    def _update_ongoing_conversations_memory(self):
        """Update long-term memory for ongoing conversations that didn't end naturally"""
        processed_pairs = set()
        
        for agent_name in self.environment.agent_states.keys():
            memory = self.memory_manager.get_short_term_memory(agent_name)
            if not memory or "current_conversation" not in memory or not memory["current_conversation"].get("partner"):
                continue
                
            partner = memory["current_conversation"]["partner"]
            
            if not partner or (agent_name, partner) in processed_pairs or (partner, agent_name) in processed_pairs:
                continue
                
            # Mark this pair as processed
            processed_pairs.add((agent_name, partner))
            
            # Get the full conversation history
            exchanges = memory["current_conversation"].get("exchanges", [])
            if exchanges and len(exchanges) > 0:
                # Check if conversation didn't end naturally (no END OF CONVERSATION marker)
                conversation_ended_naturally = any("<END OF CONVERSATION>" in resp for exchange in exchanges for resp in exchange.values())
                
                if not conversation_ended_naturally:
                    # Convert exchanges to the format expected by generate_long_term_memory
                    conversation_history = []
                    for exchange in exchanges:
                        conversation_history.append(exchange)
                    
                    # Generate long-term memory for ongoing conversations
                    try:
                        agent1_memory_summary = self.generate_long_term_memory(agent_name, partner, conversation_history)
                        agent2_memory_summary = self.generate_long_term_memory(partner, agent_name, conversation_history)
                        
                        # Update long-term memory for both agents
                        self.memory_manager.update_long_term_memory(agent_name, partner, agent1_memory_summary)
                        self.memory_manager.update_long_term_memory(partner, agent_name, agent2_memory_summary)
                        
                        print(f"{bcolors.OKGREEN}✅ Updated ongoing conversation memory for {agent_name} and {partner}{bcolors.ENDC}")
                        
                    except Exception as e:
                        print(f"{bcolors.FAIL}Error updating ongoing conversation memory for {agent_name} and {partner}: {e}{bcolors.ENDC}")

    def print_memory_status(self, agent_id: str = None):
        """Print the current memory status for debugging purposes"""
        if agent_id:
            # Print memory for specific agent
            long_term = self.memory_manager.get_long_term_memory(agent_id)
            short_term = self.memory_manager.get_short_term_memory(agent_id)
            
            print(f"\n{bcolors.HEADER}=== Memory Status for {agent_id} ==={bcolors.ENDC}")
            print(f"{bcolors.OKCYAN}Long-term memory entries: {len(long_term.get('agent_insights', {}))}{bcolors.ENDC}")
            for other_agent, memory in long_term.get('agent_insights', {}).items():
                print(f"  - {other_agent}: {memory[:100]}...")
            
            print(f"{bcolors.OKCYAN}Short-term memory:{bcolors.ENDC}")
            if short_term.get('current_conversation', {}).get('partner'):
                print(f"  - Current partner: {short_term['current_conversation']['partner']}")
                print(f"  - Exchanges: {len(short_term['current_conversation'].get('exchanges', []))}")
            else:
                print("  - No current conversation")
        else:
            # Print memory for all agents
            print(f"\n{bcolors.HEADER}=== Overall Memory Status ==={bcolors.ENDC}")
            for agent_name in self.environment.agent_states.keys():
                long_term = self.memory_manager.get_long_term_memory(agent_name)
                short_term = self.memory_manager.get_short_term_memory(agent_name)
                
                print(f"{bcolors.OKCYAN}{agent_name}:{bcolors.ENDC}")
                print(f"  - Long-term entries: {len(long_term.get('agent_insights', {}))}")
                if short_term.get('current_conversation', {}).get('partner'):
                    print(f"  - Current partner: {short_term['current_conversation']['partner']}")
                    print(f"  - Exchanges: {len(short_term['current_conversation'].get('exchanges', []))}")

    def simulate_conversations(self) -> List[Dict[str, Any]]:
        """Simulate multiple conversations between different agent pairs"""
        conversation_pairs = self.environment.get_conversation_pairs()
        conversation_count = 0
        all_histories = []

        print(f"\n{'📊 Simulation Overview 📊':^88}")
        print("=" * 80)
        if self.cfg.environment.type == "time_dependent":
            print(f"Total possible conversations: {self.environment.total_possible_conversations}")
        else:
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
                print(f"\n{bcolors.OKGREEN}📝 Conversation saved to: {pair_log_path}{bcolors.ENDC}")

                all_histories.append({
                    "pair": (agent1, agent2),
                    "dialogue": history
                })
                conversation_count += 1
        else:
            print(f"\n{bcolors.HEADER}=== Starting Time-Dependent Environment Simulation ==={bcolors.ENDC}")
            max_time_steps = self.cfg.environment.settings.time_dependent.max_time_steps
            
            for t in range(max_time_steps):
                self.environment.start_new_time_step()
                print(f"\n{bcolors.HEADER}--- Time Step {t + 1}/{max_time_steps} ---{bcolors.ENDC}")
                
                current_pairs = self.environment.get_conversation_pairs()
                
                for agent1, agent2 in current_pairs:
                    print(f"Delaying conversation between {agent1} and {agent2} for 60 seconds.")
                    # time.sleep(60)
                    # Get memory context
                    memory = self.get_memory_context(agent1, agent2)
                    if memory["conversation_summary"]:
                        print(f"\n{bcolors.OKCYAN}📜 Previous conversation context:{bcolors.ENDC}")
                        print(f"{bcolors.OKCYAN}{memory['conversation_summary']}{bcolors.ENDC}")
                    
                    # Continue conversation while within time step limit
                    while self.environment.should_continue_conversation(agent1, agent2):
                        # Simulate one exchange
                        turn_responses = {}
                        
                        for speaker, listener in [(agent1, agent2), (agent2, agent1)]:
                            agent_data = self.agent_manager.get_agent(speaker)
                            if not agent_data:
                                continue
                            
                            short_term_mem = self.memory_manager.get_short_term_memory(speaker)
                            last_exchange = short_term_mem['current_conversation']['exchanges'][-1] if len(short_term_mem['current_conversation']['exchanges']) > 0 else ""
                            
                            # Build prompt with memory context
                            memory_context = ""
                            if memory["previous_insights_about_partner"]:
                                memory_context += f"\nWhat you know about {listener}: {memory['previous_insights_about_partner']}"
                            if memory["partner_previous_insights"]:
                                memory_context += f"\nWhat {listener} knows about you: {memory['partner_previous_insights']}"
                            if memory["conversation_summary"]:
                                memory_context += f"\n\nPrevious conversation:\n{memory['conversation_summary']}"
                            
                            memory_context += f"\n\nThe conversation till this point:\n {last_exchange}\n{turn_responses}"
                            
                            # Get conversation history
                            short_term_mem = self.memory_manager.get_short_term_memory(speaker)
                            total_messages_exchanged = len(short_term_mem['current_conversation']['exchanges'])*2
                            # print(f"Agent {speaker} personality: length of conversation: {len(memory_context)}")
                            
                            # Choose prompt template based on agent's data format
                            is_txt_personality = isinstance(agent_data["personality"], str)
                            prompt_template = self.txt_prompt_template if is_txt_personality else self.yaml_prompt_template
                            
                            if is_txt_personality:
                                # For TXT files, the entire content is the personality
                                prompt = prompt_template.format(
                                    agent_curr_bingo_board=self.bingo_manager.get_agent_bingo(speaker),
                                    num_filled_squares=self.bingo_manager.get_agent_board_state(speaker)["filled_squares"],
                                    num_unfilled_squares=self.bingo_manager.get_agent_board_state(speaker)["unfilled_squares"],
                                    name=speaker,
                                    other_name=listener,
                                    conversation_summary=memory_context,
                                    current_turn = t,
                                    total_turns = max_time_steps,
                                    messages_exchanged=self.environment.agent_states[speaker].messages_in_current_conversation,
                                    max_messages=self.cfg.environment.settings.time_dependent.max_messages_per_conversation,
                                    total_conversation_messages_exchanged=total_messages_exchanged,
                                    past_partners_agent1=self.environment.agent_states[speaker].past_partners,
                                    past_partners_agent2=self.environment.agent_states[listener].past_partners,
                                    last_exchange=last_exchange,
                                    personality=agent_data["personality"]  # Pass entire content as personality
                                )
                            else:
                                # For YAML files, unpack all personality fields
                                prompt = prompt_template.format(
                                    agent_curr_bingo_board=self.bingo_manager.get_agent_bingo(speaker),
                                    num_filled_squares=self.bingo_manager.get_agent_board_state(speaker)["filled_squares"],
                                    num_unfilled_squares=self.bingo_manager.get_agent_board_state(speaker)["unfilled_squares"],
                                    name=speaker,
                                    other_name=listener,
                                    conversation_summary=memory_context,
                                    current_turn = t,
                                    total_turns = max_time_steps,
                                    messages_exchanged=self.environment.agent_states[speaker].messages_in_current_conversation,
                                    max_messages=self.cfg.environment.settings.time_dependent.max_messages_per_conversation,
                                    total_conversation_messages_exchanged=total_messages_exchanged,
                                    past_partners_agent1=self.environment.agent_states[speaker].past_partners,
                                    past_partners_agent2=self.environment.agent_states[listener].past_partners,
                                    last_exchange=last_exchange,
                                    **agent_data["personality"]  # Unpack all personality fields from YAML
                                )
                            
                            # prompt_tokens = len(str(prompt)) // 4
                            # print(f"🗣️  {speaker} submitting prompt with ~{prompt_tokens} tokens...")
                            
                            try:
                                response = self.agent_manager.safe_get_response(agent_data["agent"], prompt)
                                if response:
                                    # Strip out bingo tags if present
                                    if "<FILL IN BINGO>" in response:
                                        bingo_text = response.split("<FILL IN BINGO>")[1].split("</FILL IN BINGO>")[0]
                                        response = response.replace(f"<FILL IN BINGO>{bingo_text}</FILL IN BINGO>", "")
                                        
                                        # Check if there's a meaningful context for the bingo filling
                                        should_update = True
                                        
                                        # If this is the first exchange, don't allow bingo filling
                                        if not short_term_mem or len(short_term_mem['current_conversation']['exchanges']) <= 1:
                                            print(f"\n{bcolors.WARNING}⚠️ {speaker} attempted to fill bingo too early in the conversation. Ignoring.{bcolors.ENDC}")
                                            should_update = False
                                        else:
                                            # Get the last exchange from the other participant
                                            last_exchanges = short_term_mem['current_conversation']['exchanges']
                                            other_participant_messages = []
                                            
                                            # Collect the last 2 messages from the other participant
                                            for exchange in reversed(last_exchanges):
                                                if listener in exchange:
                                                    other_participant_messages.append(exchange[listener])
                                                    if len(other_participant_messages) >= 2:
                                                        break
                                            
                                            # Check if the bingo text is related to what the other participant said
                                            if not other_participant_messages:
                                                print(f"\n{bcolors.WARNING}⚠️ No previous messages from {listener} found. Ignoring bingo attempt.{bcolors.ENDC}")
                                                should_update = False
                                            else:
                                                # Combine the other participant's messages
                                                other_text = " ".join(other_participant_messages)
                                                
                                                # Check for keyword overlap between bingo text and other's messages
                                                bingo_keywords = [w.lower() for w in re.findall(r"\b\w+\b", bingo_text) if len(w) > 3]
                                                other_keywords = [w.lower() for w in re.findall(r"\b\w+\b", other_text) if len(w) > 3]
                                                
                                                # Calculate overlap
                                                overlap = [w for w in bingo_keywords if w in other_keywords]
                                                
                                                if len(overlap) < 2 and (len(bingo_keywords) == 0 or len(overlap) / len(bingo_keywords) < 0.2):
                                                    print(f"\n{bcolors.WARNING}⚠️ Bingo attempt by {speaker} doesn't match conversation context. Ignoring.{bcolors.ENDC}")
                                                    should_update = False
                                        
                                        # Only update if there's a meaningful context
                                        if should_update:
                                            self.bingo_manager.update_agent_bingo(speaker, bingo_text, matched_agent=listener)
                                            print(f"\n{bcolors.OKGREEN}✅ Bingo board updated for {speaker} with the content: {bingo_text}{bcolors.ENDC}")
                                    
                                    # Format and print the response
                                    color = bcolors.OKBLUE if speaker == agent1 else bcolors.OKGREEN
                                    print(self._format_message(speaker, response, color))
                                    turn_responses[speaker] = response

                                    if self.token_counter:
                                        self.token_counter.add_api_call(prompt=prompt, response=response)
                            except Exception as e:
                                print(f"\n{bcolors.FAIL}❌ Error during {speaker}'s turn: {e}{bcolors.ENDC}")
                                continue
                        
                        if turn_responses:
                            # Update memory after each exchange
                            self.update_conversation_memory(agent1, agent2, turn_responses)
                            
                            # Check for conversation end
                            conversation_ended = False
                            
                            # Check if any response has end marker
                            for response in turn_responses.values():
                                if "<END OF CONVERSATION>" in response:
                                    conversation_ended = True
                                    speaker_mem = self.memory_manager.get_short_term_memory(agent1) or self.memory_manager.get_short_term_memory(agent2)
                                    exchanges = len(speaker_mem['current_conversation']['exchanges']) if speaker_mem else 'unknown'
                                    print(f"\n{bcolors.OKGREEN}🏁 Conversation naturally ended after {exchanges} exchanges{bcolors.ENDC}")
                                    
                                    # Update long-term memory when conversation ends
                                    try:
                                        # Get full conversation history
                                        agent1_mem = self.memory_manager.get_short_term_memory(agent1)
                                        agent2_mem = self.memory_manager.get_short_term_memory(agent2)
                                        
                                        if agent1_mem and agent1_mem.get("current_conversation", {}).get("exchanges"):
                                            conversation_history = agent1_mem["current_conversation"]["exchanges"]
                                            
                                            # Generate long-term memory for both agents
                                            agent1_memory_summary = self.generate_long_term_memory(agent1, agent2, conversation_history)
                                            agent2_memory_summary = self.generate_long_term_memory(agent2, agent1, conversation_history)
                                            
                                            # Update long-term memory
                                            self.memory_manager.update_long_term_memory(agent1, agent2, agent1_memory_summary)
                                            self.memory_manager.update_long_term_memory(agent2, agent1, agent2_memory_summary)
                                            
                                            print(f"{bcolors.OKGREEN}✅ Updated long-term memory for {agent1} and {agent2} after conversation ended{bcolors.ENDC}")
                                            
                                    except Exception as e:
                                        print(f"{bcolors.FAIL}Error updating long-term memory after conversation ended: {e}{bcolors.ENDC}")
                            
                            # Update agent states
                            self.environment.update_agent_states(agent1, agent2, ended=conversation_ended)
                            
                            if conversation_ended:
                                break
                        else:
                            break
                
                # Process all conversations at the end of the time step
                self.end_time_step()
                
                # Update long-term memory for any ongoing conversations that didn't end naturally
                self._update_ongoing_conversations_memory()
                
                # Print agent statistics at the end of each time step
                self.environment.print_agent_stats()

                # Save token usage summary at the end of each time step
                if self.token_counter:
                    self.token_counter.save_summary(self.cfg.paths.outputs_dir)
                
                if self.environment.experiment_complete:
                    print(f"\n{bcolors.OKGREEN}🎉 All possible conversations have been completed!{bcolors.ENDC}")
                    break
            
            print("\n" + "=" * 80)
            print(f"{bcolors.HEADER}{'📊 Simulation Complete 📊':^88}{bcolors.ENDC}")
            print(f"{bcolors.HEADER}{f'Total conversations: {conversation_count}'.center(88)}{bcolors.ENDC}")
            print(f"{bcolors.HEADER}{f'Time steps used: {t + 1}/{max_time_steps}'.center(88)}{bcolors.ENDC}")
            print("=" * 80)
        
        return all_histories 