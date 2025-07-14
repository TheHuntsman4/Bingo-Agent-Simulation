import os
import json

def log_conversation(exchange_id, exchange_content, out_path):
    if not os.path.exists(out_path):
        os.makedirs(out_path, exist_ok=True)
        
    if os.path.exists(out_path):
        with open(out_path, "r") as f:
            data = json.load(f)
    else:
        data = {}
    
    data[exchange_id] = exchange_content
    
    with open(out_path, "w") as f:
        json.dump(data, f)
