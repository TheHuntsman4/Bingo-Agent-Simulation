import os
import json
import uuid
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from utils.token_counter import TokenCounter

# Global token counter that can be set from outside
global_token_counter = None

def generate_conversation_id():
    return uuid.uuid4().hex[:8]

def log_conversation(exchange_id, exchange_content, out_path):
    if os.path.exists(out_path):
        with open(out_path, "r") as f:
            data = json.load(f)
    else:
        data = {}

    data[exchange_id] = exchange_content

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
