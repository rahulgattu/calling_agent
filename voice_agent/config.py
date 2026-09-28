"""Environment-backed configuration for the voice agent."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PRINCIPAL_CONTEXT_FILE = PROJECT_ROOT / "principal_context.md"
# Keep the local project's .env authoritative over stale shell variables.
load_dotenv(PROJECT_ROOT / ".env", override=True)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    groq_api_key: str
    deepgram_api_key: str
    cartesia_api_key: str
    cartesia_voice_id: str
    groq_model: str = "openai/gpt-oss-120b"
    school_context: str = ""
    browser_input_sample_rate: int = 16_000
    output_sample_rate: int = 24_000

    @classmethod
    def from_environment(cls) -> "Settings":
        required = {
            "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
            "DEEPGRAM_API_KEY": os.getenv("DEEPGRAM_API_KEY"),
            "CARTESIA_API_KEY": os.getenv("CARTESIA_API_KEY"),
            "CARTESIA_VOICE_ID": os.getenv("CARTESIA_VOICE_ID"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"Missing server configuration: {', '.join(missing)}")

        school_context = (
            PRINCIPAL_CONTEXT_FILE.read_text(encoding="utf-8").strip()
            if PRINCIPAL_CONTEXT_FILE.is_file()
            else ""
        )

        return cls(
            groq_api_key=required["GROQ_API_KEY"],
            deepgram_api_key=required["DEEPGRAM_API_KEY"],
            cartesia_api_key=required["CARTESIA_API_KEY"],
            cartesia_voice_id=required["CARTESIA_VOICE_ID"],
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            school_context=school_context,
        )

    @staticmethod
    def warn_if_incomplete() -> None:
        names = ("GROQ_API_KEY", "DEEPGRAM_API_KEY", "CARTESIA_API_KEY", "CARTESIA_VOICE_ID")
        missing = [name for name in names if not os.getenv(name)]
        if missing:
            logger.warning("Missing environment variables: %s", ", ".join(missing))
