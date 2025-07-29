import os
import json
import uuid
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from utils.token_counter import TokenCounter

# Global token counter that can be set from outside
global_token_counter = None

def generate_conversation_id():
    return str(uuid.uuid4())

def digest_conversation(prev_digest, history):
    model = ChatGoogleGenerativeAI(
        model="gemma-3-27b-it",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.1,
    )
    prompt = PromptTemplate(
        input_variables=["prev_digest", "history"],
        template="""You are a helpful assistant.
        Here is the previous digest of the conversation: {prev_digest}
        Here is the history of the conversation: {history}
        Please digest the conversation and return a concise summary (less than 50 words).
        """
    )
    formatted_prompt = prompt.format(prev_digest=prev_digest, history=history)
    response = model.invoke(formatted_prompt)
    
    # Track token usage if counter is available
    if global_token_counter is not None:
        global_token_counter.add_api_call(
            prompt=formatted_prompt,
            response=response.content if hasattr(response, 'content') else str(response)
        )
    
    return response

def log_conversation(exchange_id, exchange_content, out_path):
    if os.path.exists(out_path):
        with open(out_path, "r") as f:
            data = json.load(f)
    else:
        data = {}

    data[exchange_id] = exchange_content

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
