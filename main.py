from config import settings
from providers.groq import GroqClient
from agent import SYMAgent

client = GroqClient(settings.GROQ_KEY_1)
# print([{k: v} for k, v in vars(Config).items() if not k.startswith("_")])

agent = SYMAgent(client)
agent.agent_loop(
    "Could you write me a essay on the 21st century ai and summarize the usage of react in frontnend industry."
)
