import os
import json
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Load API Key
load_dotenv("./.env")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise EnvironmentError("GOOGLE_API_KEY is missing from environment.")

# Initialize model
model = ChatGoogleGenerativeAI(
    model="gemma-3-27b-it",
    google_api_key=GOOGLE_API_KEY,
    temperature=0.3,
)

# Load CSV
csv_path = "alumni_censored_simple.csv"
df = pd.read_csv(csv_path)
print(f"✅ Loaded {len(df)} survey records")

# Load JSON
json_path = "alumni-simple-boards.json"
with open(json_path, 'r') as f:
    bingo_data = json.load(f)
print(f"✅ Loaded {len(bingo_data)} bingo boards")

# Create a map from owner -> bingo items
bingo_map = {}
for board in bingo_data:
    owner = board.get("owner")
    if not owner:
        continue
    items = []
    for row in board["squares"]:
        for square in row:
            if square.get("owner") == owner or square.get("owner") is None:
                items.append(square["text"])
    bingo_map[owner.strip()] = items

# Prompt builder
def create_prompt(agent_id, survey_row, bingo_items):
    demographics = "\n".join([f"{col}: {survey_row[col]}" for col in survey_row.index])
    bingo_formatted = "\n".join(f"- {item}" for item in bingo_items)

    return f"""
You are generating a detailed personality profile for an AI agent attending a live social simulation event.

Each agent has:
1. Personal demographic and interest data (from a pre-survey)
2. A Bingo board with personalized social prompts to guide interactions

Your task is to generate a structured, human-like profile with the following exact format:

---

### Name & Backstory
(Provide a name. Add a short story about the agent’s upbringing, motivations, and life experience.)

### Demographics & Cultural Background
(Summarize where the person is from, their cultural identity, values, and formative influences.)

### Professional Background & Interests
(What do they do? What are they passionate about? What problems do they care about solving?)

### Hobbies, Passions & Quirks
(List 2–4 interests or hobbies. Add one unique trait or quirky thing they love.)

### Communication Style
(How do they typically engage with others? Are they curious, shy, witty, analytical, warm?)

### Event Goals & Bingo Board Insights
(What are they looking to talk about or discover during this event? Use the Bingo prompts as inspiration for specific interests or social hooks.)

---

### Agent Input Summary:

**Agent ID**: {agent_id}

**Survey Response Summary**:
{demographics}

**Bingo Prompts**:
{bingo_formatted}

---
Please fill out the profile in the exact section structure shown above.
The tone should be human, expressive, and natural — like writing character notes for a social roleplay.

"""

# Output folder
output_dir = "../agents_personas"
os.makedirs(output_dir, exist_ok=True)

# Debugging help: track who matched
matched_agents = set()

# Generate personalities
for _, row in tqdm(df.iterrows(), total=len(df)):
    initials = str(row.get("First and last name", ""))
    print(initials)

    # Use initials as agent_id for mapping to bingo board
    if initials not in bingo_map:
        print(f"⚠️ No bingo board for agent {initials}")
        continue

    prompt = create_prompt(initials, row, bingo_map[initials])
    try:
        response = model.invoke(prompt)
        personality = response.content.strip()
        if not personality:
            print(f"❌ Empty response for {initials}")
            continue

        file_path = os.path.join(output_dir, f"{initials}.txt")
        with open(file_path, "w") as f:
            f.write(personality)
        matched_agents.add(initials)
        print(f"✅ Saved profile for {initials} -> {file_path}")
    except Exception as e:
        print(f"❌ Error generating for {initials}: {e}")

print(f"\n🔚 Done! Successfully matched and generated profiles for {len(matched_agents)} agents.")
