from dotenv import load_dotenv
from scripts.main.makeLLM import LLMClient

load_dotenv(override=True)

llm = LLMClient()

script = llm.get_script("AI aur ChatGPT ka fark kya hai")
print(script)
