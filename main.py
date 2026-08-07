from config import settings
from providers.groq import GroqClient
from providers.orclient import ORClient
from agent import SYMAgent

# client = ORClient(settings.GROQ_KEY_1)
client = GroqClient(settings.GROQ_KEY_1)
# print([{k: v} for k, v in vars(Config).items() if not k.startswith("_")])

agent = SYMAgent(client)
agent.agent_loop("Explain the  cons of masturbation.")
