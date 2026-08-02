from config import settings
from providers.groq import GroqClient as Gclient
from dotenv import load_dotenv

load_dotenv()
client = Gclient(api_key=settings.GROQ_KEY_1)
print(repr(settings.GROQ_KEY_1))


client.stream_chat()
