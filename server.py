"""Development entry point for the modular voice-agent application."""

import uvicorn

from voice_agent.app import app


if __name__ == "__main__":
    uvicorn.run("voice_agent.app:app", host="127.0.0.1", port=8000, reload=False)
