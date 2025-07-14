# Bingo Playing Agent Simulation

A simulation framework for creating and testing AI agents that can play bingo games. This project uses LangChain and Google's Gemini AI to create intelligent bingo-playing agents.

## Prerequisites

- Python 3.8 or higher
- Google AI API key (for Gemini model access)

## Setting up the project

The project uses [Astral](https://astral.sh/blog/uv) for dependency management.

```bash
# Install Astral uv on your system
pip install uv

# Clone the repository
git clone <repository-url>
cd bingo_agent_simulation_prototype

# Create and activate virtual environment
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .
```

## Environment Configuration

1. Create a `.env` file in the project root:
```bash
GOOGLE_API_KEY=your_google_ai_api_key_here
```

2. Get your Google AI API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

