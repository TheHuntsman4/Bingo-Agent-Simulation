from dotenv import load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv('./.env')

class AgentBase:
    def __init__(self):
        self.model = ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=os.getenv("GOOGLE_API_KEY"), temperature=0.1)

    def get_response(self, prompt):
        return self.model.invoke(prompt)