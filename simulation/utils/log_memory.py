import os
import json
import uuid

def generate_conversation_id():
    return str(uuid.uuid4())


def log_conversation(exchange_id, exchange_content, out_path):
    if os.path.exists(out_path):
        with open(out_path, "r") as f:
            data = json.load(f)
    else:
        data = {}

    data[exchange_id] = exchange_content

    with open(out_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
