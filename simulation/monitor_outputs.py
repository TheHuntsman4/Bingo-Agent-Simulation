#!/usr/bin/env python3
"""
Monitor script to track conversation outputs and progress
"""
import os
import json
import glob
from datetime import datetime

OUTPUTS_DIR = os.path.join(os.path.dirname(__file__), "outputs")


def monitor_outputs():
    """Monitor and display current outputs"""
    if not os.path.exists(OUTPUTS_DIR):
        print("No outputs directory found.")
        return

    print(f"=== Conversation Output Monitor ===\n")
    print(f"Outputs directory: {OUTPUTS_DIR}\n")

    # Check for progress files
    progress_files = glob.glob(os.path.join(OUTPUTS_DIR, "progress_turn_*.json"))
    progress_files.sort(key=lambda x: int(x.split("_")[-1].split(".")[0]))

    if progress_files:
        print(f"Found {len(progress_files)} progress files:")
        for pf in progress_files:
            try:
                with open(pf, "r") as f:
                    data = json.load(f)
                turn = data.get("turn", "?")
                agent = data.get("current_agent", "?")
                ended = data.get("ended_agents", [])
                print(f"  Turn {turn}: {agent} responded (Ended agents: {ended})")
            except Exception as e:
                print(f"  Error reading {pf}: {e}")
    else:
        print("No progress files found yet.")

    # Check for final conversation log
    log_files = glob.glob(os.path.join(OUTPUTS_DIR, "conversation_log_*.json"))
    if log_files:
        print(f"\nFound {len(log_files)} conversation log(s):")
        for lf in log_files:
            try:
                with open(lf, "r") as f:
                    data = json.load(f)
                exchange_id = list(data.keys())[0] if data else "unknown"
                messages = data.get(exchange_id, [])
                print(
                    f"  {os.path.basename(lf)}: {len(messages)} messages in {exchange_id}"
                )
            except Exception as e:
                print(f"  Error reading {lf}: {e}")

    # Show latest conversation if available
    if progress_files:
        latest_progress = progress_files[-1]
        try:
            with open(latest_progress, "r") as f:
                data = json.load(f)
            conversation = data.get("conversation_so_far", [])
            if conversation:
                print(f"\n=== Latest Conversation (Turn {data.get('turn', '?')}) ===")
                for msg in conversation[-5:]:  # Show last 5 messages
                    print(f"  {msg}")
        except Exception as e:
            print(f"Error reading latest progress: {e}")


if __name__ == "__main__":
    monitor_outputs()
