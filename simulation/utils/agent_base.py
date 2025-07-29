from dotenv import load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI

env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env'))
print(f"Loading .env from: {env_path}")
load_dotenv(env_path)


class AgentBase:
    def __init__(self):
        self.model = ChatGoogleGenerativeAI(
            model="gemma-3-27b-it",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.1,
        )

    def get_response(self, prompt):
        agent_response = self.model.invoke(prompt)
        return agent_response.content
