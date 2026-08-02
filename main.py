from config import Config
from dotenv import load_dotenv

load_dotenv()

print([{k: v} for k, v in vars(Config).items() if not k.startswith("_")])
