#!/usr/bin/env python3
"""
Test script to verify long-term memory updates are working correctly.
"""

import os
import sys
import json
from pathlib import Path

# Add the simulation directory to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from simulation.environments.time_dependent.memory_manager import MemoryManager
from omegaconf import OmegaConf

def test_memory_manager():
    """Test the memory manager functionality"""
    
    # Create a simple config for testing
    config = OmegaConf.create({
        'paths': {
            'base_dir': '/tmp/test_simulation',
            'outputs_dir': 'outputs',
            'agent_memories_dir': 'agent_memories',
            'long_term_memories': 'long_term',
            'short_term_memories': 'short_term'
        },
        'experiment': {
            'experiment_id': 'test_memory_fix'
        }
    })
    
    # Create memory manager
    memory_manager = MemoryManager(config)
    
    # Test short-term memory updates
    print("Testing short-term memory updates...")
    memory_manager.update_short_term_memory("Alice", "Bob", {"Alice": "Hello Bob!"})
    memory_manager.update_short_term_memory("Alice", "Bob", {"Bob": "Hi Alice!"})
    
    # Check short-term memory
    alice_short = memory_manager.get_short_term_memory("Alice")
    print(f"Alice's short-term memory: {alice_short}")
    
    # Test long-term memory updates
    print("\nTesting long-term memory updates...")
    memory_manager.update_long_term_memory("Alice", "Bob", "Alice learned that Bob is friendly and likes to chat.")
    memory_manager.update_long_term_memory("Bob", "Alice", "Bob found Alice to be outgoing and curious.")
    
    # Check long-term memory
    alice_long = memory_manager.get_long_term_memory("Alice")
    bob_long = memory_manager.get_long_term_memory("Bob")
    
    print(f"Alice's long-term memory: {alice_long}")
    print(f"Bob's long-term memory: {bob_long}")
    
    # Test memory file creation
    alice_file = os.path.join(config.paths.base_dir, config.paths.outputs_dir, 
                             config.paths.agent_memories_dir, config.experiment.experiment_id,
                             config.paths.long_term_memories, "Alice.json")
    
    if os.path.exists(alice_file):
        print(f"\n✅ Long-term memory file created successfully: {alice_file}")
        with open(alice_file, 'r') as f:
            content = json.load(f)
            print(f"File content: {content}")
    else:
        print(f"\n❌ Long-term memory file not found: {alice_file}")
    
    print("\n✅ Memory manager test completed successfully!")

if __name__ == "__main__":
    test_memory_manager() 