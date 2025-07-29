"""Simple utility to track API token usage"""
import json
import os
from datetime import datetime

class TokenCounter:
    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.calls = []
    
    def add_api_call(self, prompt=None, response=None):
        """Extract token counts from an API call"""
        # Rough estimation: ~4 chars per token
        prompt_tokens = len(str(prompt)) // 4 if prompt else 0
        completion_tokens = len(str(response)) // 4 if response else 0
        
        # Update totals
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens += (prompt_tokens + completion_tokens)
        
        # Record the call
        self.calls.append({
            'timestamp': datetime.now().isoformat(),
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': prompt_tokens + completion_tokens
        })
    
    def save_summary(self, output_dir):
        """Save token usage summary to a file"""
        summary = {
            'timestamp': datetime.now().isoformat(),
            'total_prompt_tokens': self.total_prompt_tokens,
            'total_completion_tokens': self.total_completion_tokens,
            'total_tokens': self.total_tokens,
            'total_calls': len(self.calls),
            'calls': self.calls
        }
        
        # Create output filename with timestamp
        filename = f'token_usage_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        
        return filepath
    
    def print_summary(self):
        """Print token usage summary"""
        print("\n=== Token Usage Summary ===")
        print(f"Total Prompt Tokens: {self.total_prompt_tokens:,}")
        print(f"Total Completion Tokens: {self.total_completion_tokens:,}")
        print(f"Total Tokens: {self.total_tokens:,}")
        print(f"Total API Calls: {len(self.calls)}")
        print("============================") 