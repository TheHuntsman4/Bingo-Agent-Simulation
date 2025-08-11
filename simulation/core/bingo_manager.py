import os
import json
import re
from typing import Dict, Any
from omegaconf import DictConfig

class BingoManager:
    def __init__(self, cfg: DictConfig):
        self.cfg = cfg

    def get_agent_bingo(self, agent_name: str) -> Dict[str, Any]:
        """Loads and returns an agent's bingo board from file"""
        path = os.path.join(self.cfg.paths.bingo_output_dir, f"{agent_name}.json")
        if not os.path.exists(path):
            return {}
        with open(path, "r") as f:
            return json.load(f)
        
    def get_agent_board_state(self, agent_name: str) -> Dict[str, Any]:
        """Gets the current state of an agent's bingo board including filled/unfilled squares"""
        path = os.path.join(self.cfg.paths.bingo_output_dir, f"{agent_name}.json")
        if not os.path.exists(path):
            return {"filled_squares": 0, "unfilled_squares": 0}
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
        Checks if a response matches a bingo clue using a more strict matching algorithm.
        Requirements:
        1. At least 40% of significant clue keywords must match
        2. At least 2 significant keywords must match
        3. The matched keywords must appear in a similar context
        """
        # Normalize text
        clue = clue.lower().strip()
        response = response.lower().strip()
        
        # Get significant keywords (words longer than 3 chars, excluding common words)
        common_words = {'find', 'someone', 'who', 'with', 'that', 'have', 'has', 'had', 'been', 'were', 'are', 'will', 'would', 'could', 'should', 'about', 'their', 'there', 'from', 'your', 'this', 'that', 'these', 'those', 'them', 'they', 'into', 'over', 'under', 'again', 'once', 'here', 'there', 'when', 'where', 'what', 'which', 'while', 'want', 'wanted', 'wants', 'like', 'likes', 'liked'}
        
        clue_keywords = [word for word in re.findall(r'\b\w+\b', clue) 
                        if len(word) > 3 and word not in common_words]
        
        if not clue_keywords:
            return False
            
        # Find matches in response
        matched_keywords = []
        for keyword in clue_keywords:
            # Look for exact matches or close variations
            if re.search(rf'\b{keyword}s?\b', response):  # Handles singular/plural
                matched_keywords.append(keyword)
                
        # Calculate match percentage
        match_percentage = len(matched_keywords) / len(clue_keywords)
        
        # Check context - keywords should appear close to each other
        if len(matched_keywords) >= 2:
            # Find the positions of all matched keywords in the response
            positions = []
            for keyword in matched_keywords:
                match = re.search(rf'\b{keyword}s?\b', response)
                if match:
                    positions.append(match.start())
            
            # Sort positions
            positions.sort()
            
            # Check if matched keywords are within reasonable distance (100 chars)
            max_distance = 100
            for i in range(len(positions) - 1):
                if positions[i + 1] - positions[i] > max_distance:
                    return False
            
        # Return True only if both percentage and count thresholds are met
        return match_percentage >= 0.4 and len(matched_keywords) >= 2

    def update_agent_bingo(self, agent_name: str, response: str, matched_agent: str) -> None:
        """Updates an agent's bingo board when they match a square during conversation"""
        path = os.path.join(self.cfg.paths.bingo_output_dir, f"{agent_name}.json")
        if not os.path.exists(path):
            return

        with open(path, "r") as f:
            board = json.load(f)

        updated = False
        # Check each unfilled square for matches
        for square in board["squares"]:
            if not square.get("filled"):
                clue = square.get("text", "").lower()
                
                # Skip very short clues to avoid false positives
                if len(clue.split()) < 2:
                    continue
                    
                if self.keyword_match(clue, response.lower()):
                    # Make sure response is substantial enough
                    if len(response.split()) < 5:
                        continue
                        
                    square["filled"] = True
                    square["matched_with"] = matched_agent
                    square["response_snippet"] = response
                    updated = True
                    print(f"\nMatch found for bingo square: '{clue}'")
                    print(f"Response that matched: '{response}'")
                    break  # Only fill one square per response

        if updated:
            with open(path, "w") as f:
                json.dump(board, f, indent=2)