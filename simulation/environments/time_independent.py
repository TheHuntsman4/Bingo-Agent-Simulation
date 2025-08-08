from typing import List, Dict, Any, Tuple
from .base_environment import BaseEnvironment

class TimeIndependentEnvironment(BaseEnvironment):
    """
    Time-independent, round-wise pairing of agents.
    - Each round is a maximal matching (every agent talks to at most one partner).
    - Conversations are simulated to completion (per turns_per_conversation or end marker).
    - Bingo updates continue to be handled by ConversationManager on each response.
    """
    def __init__(self, cfg, agent_manager):
        super().__init__(cfg, agent_manager)
        self.agent_names = self.agent_manager.get_agent_names()
        self.rounds: List[List[Tuple[str, str]]] = self._build_round_robin_schedule(self.agent_names)
        self.total_rounds = len(self.rounds)

        # Map pair -> round index (for nice prompt context)
        self.pair_to_round: Dict[Tuple[str, str], int] = {}
        for r_idx, pairs in enumerate(self.rounds, start=1):
            for a, b in pairs:
                key = (a, b) if a < b else (b, a)
                self.pair_to_round[key] = r_idx

        # Flatten once for ConversationManager's non-time_dependent flow
        self._flat_pairs: List[Tuple[str, str]] = []
        for pairs in self.rounds:
            self._flat_pairs.extend(pairs)

    # --------- Round-robin scheduling (circle method) ---------
    def _build_round_robin_schedule(self, names: List[str]) -> List[List[Tuple[str, str]]]:
        """
        Returns a list of rounds, each a list of (a,b) pairs.
        Uses the classic "circle method". If odd, adds a BYE.
        """
        names = list(names)
        n = len(names)
        if n < 2:
            return []

        # If odd number of agents, add a BYE placeholder
        bye = None
        if n % 2 == 1:
            names.append("__BYE__")
            bye = "__BYE__"
            n += 1

        # Split into two halves
        fixed = names[0]
        others = names[1:]
        half = n // 2

        rounds = []
        # Build rounds
        for _ in range(n - 1):
            left = [fixed] + others[:half - 1]
            right = list(reversed(others[half - 1:]))

            pairs = []
            for a, b in zip(left, right):
                if a == bye or b == bye:
                    continue
                # normalize ordering
                pair = (a, b) if a < b else (b, a)
                pairs.append(pair)

            rounds.append(pairs)

            # rotate "others"
            others = [others[-1]] + others[:-1]

        return rounds

    # --------- BaseEnvironment API ---------
    def get_conversation_pairs(self) -> List[tuple]:
        """
        Return all pairs once, ordered by rounds (so they appear grouped in output).
        ConversationManager (non time_dependent branch) will iterate these and
        fully simulate each conversation immediately.
        """
        return self._flat_pairs

    def should_continue_conversation(self, history: List[Dict[str, str]]) -> bool:
        """
        Time-independent stopping rules:
        - Continue if no history yet
        - Stop if turns_per_conversation reached
        - Stop if the last turn has an <END OF CONVERSATION> marker
        """
        if not history:
            return True

        # max turns
        if len(history) >= self.cfg.conversation.conversation.turns_per_conversation:
            return False

        # end marker
        last_turn = history[-1]
        for resp in last_turn.values():
            if "<END OF CONVERSATION>" in resp:
                return False

        return True

    def get_conversation_context(self, agent1: str, agent2: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
        """
        Provide nice, stable context for prompts. ConversationManager already passes
        these into your prompt template.
        """
        key = (agent1, agent2) if agent1 < agent2 else (agent2, agent1)
        round_index = self.pair_to_round.get(key, None)

        return {
            "current_turn": len(history) if history else 0,
            "max_turns": self.cfg.conversation.conversation.turns_per_conversation,
            "round_index": round_index,
            "total_rounds": self.total_rounds
        }
