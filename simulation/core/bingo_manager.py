import os
import json
import re
from typing import Dict, Any
from omegaconf import DictConfig

class BingoManager:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg

    def keyword_match(self, clue: str, response: str) -> bool:
        """Check if any keywords from the clue match in the response"""
        clue_keywords = re.findall(r"\b\w+\b", clue)
        return any(word in response for word in clue_keywords if len(word) > 3)

    def update_agent_bingo(self, agent_name: str, response: str, matched_agent: str) -> None:
        """Update an agent's bingo board based on their response"""
        path = os.path.join(self.cfg.paths.bingo_output_dir, f"{agent_name}_bingo.json")
        if not os.path.exists(path):
            return

        with open(path, "r") as f:
            board = json.load(f)

        updated = False
        for row in board["squares"]:
            for square in row:
                if not square.get("filled", False):
                    clue = square.get("text", "").lower()
                    if self.keyword_match(clue, response.lower()):
                        square["filled"] = True
                        square["matched_with"] = matched_agent
                        square["response_snippet"] = response
                        updated = True

        if updated:
            with open(path, "w") as f:
                json.dump(board, f, indent=2) 