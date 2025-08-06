import os
import json
import re
from typing import Dict, Any
from omegaconf import DictConfig

class BingoManager:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg


    def get_agent_bingo(self, agent_name: str) -> Dict[str, Any]:
        """Get an agent's bingo board"""
        path = os.path.join(self.cfg.paths.bingo_output_dir, f"{agent_name}.json")
        if not os.path.exists(path):
            return
        with open(path, "r") as f:
            return json.load(f)
        
    def get_agent_board_state(self, agent_name: str) -> Dict[str, Any]:
        """Get an agent's bingo board state"""
        path = os.path.join(self.cfg.paths.bingo_output_dir, f"{agent_name}.json")
        if not os.path.exists(path):
            return
        with open(path, "r") as f:
            board = json.load(f)
        
        total_squares = len(board["squares"])
        filled_squares = 0
        for square in board["squares"]:
            if square["filled"] != False:
                filled_squares += 1
        
        return {
            "filled_squares": filled_squares,
            "unfilled_squares": total_squares - filled_squares
        }   
        
    def keyword_match(self, clue: str, response: str) -> bool:
        """
        Check if the clue and response have a meaningful semantic connection.
        This improved version requires more substantial matching than just single keywords.
        """
        # Extract keywords from the clue (words longer than 3 characters)
        clue_keywords = [word.lower() for word in re.findall(r"\b\w+\b", clue) if len(word) > 3]
        
        if not clue_keywords:
            return False
            
        # Count how many keywords match
        matched_keywords = [word for word in clue_keywords if word in response.lower()]
        
        # Calculate match percentage based on keywords
        if len(clue_keywords) > 0:
            match_percentage = len(matched_keywords) / len(clue_keywords)
        else:
            return False
            
        # Require at least 30% of keywords to match or at least 2 significant keywords
        return match_percentage >= 0.3 or len(matched_keywords) >= 2

    def update_agent_bingo(self, agent_name: str, response: str, matched_agent: str) -> None:
        """
        Update an agent's bingo board based on their response and conversation context.
        Only updates if there's a meaningful match between the clue and response.
        """
        path = os.path.join(self.cfg.paths.bingo_output_dir, f"{agent_name}.json")
        if not os.path.exists(path):
            return

        with open(path, "r") as f:
            board = json.load(f)

        updated = False
        # Board structure is now a flat list of squares
        for square in board["squares"]:
            if not square.get("filled"):
                clue = square.get("text", "").lower()
                
                # Skip very short clues as they're likely to cause false positives
                if len(clue.split()) < 2:
                    continue
                    
                if self.keyword_match(clue, response.lower()):
                    # Additional check: make sure the response is substantial enough
                    if len(response.split()) < 5:
                        continue
                        
                    square["filled"] = True
                    square["matched_with"] = matched_agent
                    square["response_snippet"] = response
                    updated = True
                    print(f"Match found for '{clue}' in response")
                    break  # Only fill one square per response

        if updated:
            with open(path, "w") as f:
                json.dump(board, f, indent=2)