import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
API_KEY = os.getenv("API_KEY")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")


def validate_config() -> None:
    """Raise ValueError at startup if any required environment variable is absent."""
    required = {
        "API_KEY": API_KEY,
        "CLIENT_SECRET": CLIENT_SECRET,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(
            f"Missing required environment variable(s): {', '.join(missing)}. "
            "Set them in the environment or in a .env file (see .env.example)."
        )