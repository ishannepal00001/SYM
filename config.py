from dotenv import load_dotenv
import os
from pathlib import Path

env = load_dotenv(Path(__file__).parent / ".env")
print(env)


class Config:
    GROQ_KEY_1 = os.getenv("GROQ_API_KEY_1")
    GROQ_KEY_2 = os.getenv("GROQ_API_KEY_2")
    OPENROUTER_KEY_1 = os.getenv("OPENROUTER_KEY_1")


settings = Config()
