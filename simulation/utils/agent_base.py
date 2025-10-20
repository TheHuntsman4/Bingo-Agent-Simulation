from dotenv import load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI

# loads environment variables from the parent directory's .env file
env_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../.env'))
print(f"Loading .env from: {env_path}")
load_dotenv(env_path)


class AgentBase:
    # base class that handles interactions with the Google AI model
    def __init__(self):
        # sets up the AI model with default settings
        self.model = ChatGoogleGenerativeAI(
            model="gemma-3-27b-it",
            google_api_key=os.getenv("GOOGLE_API_KEY_4"),
            temperature=0.7,
        )

    def get_response(self, prompt):
        # gets a response from the AI model for the given prompt
        agent_response = self.model.invoke(prompt)
        return agent_response.content
