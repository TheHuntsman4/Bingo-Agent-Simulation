import os
import json
from typing import Dict, Any, Optional
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult


class TokenTracker:
    """Tracks token usage for API calls"""
    
    def __init__(self):
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0
        self.total_tokens = 0
        self.api_calls = []
        
    def add_call(self, prompt_tokens: int, completion_tokens: int, model_name: str, call_type: str):
        """Add a new API call to the tracker"""
        call_info = {
            "timestamp": datetime.now().isoformat(),
            "model": model_name,
            "call_type": call_type,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens
        }
        
        self.api_calls.append(call_info)
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_tokens += (prompt_tokens + completion_tokens)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all token usage"""
        return {
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_tokens": self.total_tokens,
            "total_api_calls": len(self.api_calls),
            "api_calls": self.api_calls
        }
    
    def save_to_file(self, filepath: str):
        """Save token usage data to a JSON file"""
        data = {
            "summary": self.get_summary(),
            "timestamp": datetime.now().isoformat()
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def print_summary(self):
        """Print a summary of token usage to console"""
        print("\n" + "="*50)
        print("🔢 TOKEN USAGE SUMMARY")
        print("="*50)
        print(f"📤 Total Prompt Tokens: {self.total_prompt_tokens:,}")
        print(f"📥 Total Completion Tokens: {self.total_completion_tokens:,}")
        print(f"📊 Total Tokens: {self.total_tokens:,}")
        print(f"🔄 Total API Calls: {len(self.api_calls)}")
        print("="*50)


# Global token tracker instance
token_tracker = TokenTracker()


class TokenTrackingChatModel(BaseChatModel):
    """Wrapper for ChatGoogleGenerativeAI that tracks token usage"""
    
    def __init__(self, model_name: str = "gemma-3-27b-it", **kwargs):
        super().__init__()
        self.model = ChatGoogleGenerativeAI(model=model_name, **kwargs)
        self.model_name = model_name
    
    def invoke(self, input: Any, config: Optional[Dict] = None, **kwargs) -> ChatResult:
        """Invoke the model and track token usage"""
        try:
            # Get the response
            result = self.model.invoke(input, config, **kwargs)
            
            # Try to extract token usage from the response
            # Note: Google's API might not always return token usage in the same way
            prompt_tokens = 0
            completion_tokens = 0
            
            # Check if token usage is available in the response
            if hasattr(result, 'response_metadata') and result.response_metadata:
                metadata = result.response_metadata
                if 'token_usage' in metadata:
                    usage = metadata['token_usage']
                    prompt_tokens = usage.get('prompt_tokens', 0)
                    completion_tokens = usage.get('completion_tokens', 0)
                elif 'usage' in metadata:
                    usage = metadata['usage']
                    prompt_tokens = usage.get('prompt_tokens', 0)
                    completion_tokens = usage.get('completion_tokens', 0)
            
            # If we couldn't get token usage from metadata, estimate it
            if prompt_tokens == 0 and completion_tokens == 0:
                # Rough estimation: count characters and divide by 4 (rough token ratio)
                if isinstance(input, str):
                    prompt_tokens = len(input) // 4
                elif isinstance(input, list) and len(input) > 0:
                    # Handle list of messages
                    total_chars = sum(len(str(msg)) for msg in input)
                    prompt_tokens = total_chars // 4
                
                if hasattr(result, 'content'):
                    completion_tokens = len(str(result.content)) // 4
            
            # Track the call
            token_tracker.add_call(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                model_name=self.model_name,
                call_type="chat_completion"
            )
            
            return result
            
        except Exception as e:
            print(f"Error in token tracking wrapper: {e}")
            # Fallback to original model
            return self.model.invoke(input, config, **kwargs)
    
    @property
    def _llm_type(self) -> str:
        return "token_tracking_chat_model" 