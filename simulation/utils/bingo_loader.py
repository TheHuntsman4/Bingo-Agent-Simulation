import os
import json

def load_and_split_bingo_boards(master_path, output_dir):
    """
    Reads the master bingo board JSON and writes one JSON file per agent in the output_dir.
    Each square is augmented with tracking fields: filled, matched_with, response_snippet.
    """
    os.makedirs(output_dir, exist_ok=True)

    with open(master_path, "r") as f:
        master_boards = json.load(f)

    agent_board_paths = {}

    for board in master_boards:
        agent_name = board.get("owner")
        if not agent_name:
            continue  # skip boards with no assigned owner

        # Augment each square with bingo-tracking fields
        for row in board["squares"]:
            for square in row:
                square["filled"] = False
                square["matched_with"] = None
                square["response_snippet"] = None

        path = os.path.join(output_dir, f"{agent_name}_bingo.json")
        with open(path, "w") as f:
            json.dump(board, f, indent=2)

        agent_board_paths[agent_name] = path

    return agent_board_paths
