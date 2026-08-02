from config import settings
from dotenv import load_dotenv
from providers.groq import GroqClient
from agent import SYMAgent

load_dotenv()
client = GroqClient(settings.GROQ_KEY_1)
# print([{k: v} for k, v in vars(Config).items() if not k.startswith("_")])

agent = SYMAgent(client)
agent.agent_loop(
    "Could you write me a essay on the 21st century ai and summarize the usage or react in industry."
)
