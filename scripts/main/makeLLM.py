import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROMPT_FILE = os.path.join(_PROJECT_ROOT, "prompt.txt")


class LLMClient:

    def __init__(self, prompt_file: str = PROMPT_FILE, model: str = "gemini-2.0-flash-lite"):
        load_dotenv(override=True)
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not set. Add it to your .env file.")

        self._client = genai.Client(api_key=api_key)
        self._model_name = model
        self.prompt_file = prompt_file
        self.chat = None
        self.init_chat()

    # ------------------------------------------------------------------
    # init_chat — load prompt.txt and start a fresh Gemini chat session
    # ------------------------------------------------------------------

    def init_chat(self):
        """(Re)initialise chat using the system prompt from prompt.txt."""
        system_prompt = self._load_prompt()
        self.chat = self._client.chats.create(
            model=self._model_name,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
            ),
        )
        print(f"[LLMClient] Chat initialised -- model={self._model_name}")

    # ------------------------------------------------------------------
    # clear_memory — wipe history and reinitialise
    # ------------------------------------------------------------------

    def clear_memory(self):
        """Clear all conversation history and start fresh."""
        self.init_chat()
        print("[LLMClient] Memory cleared.")

    # ------------------------------------------------------------------
    # get_script — send a user message, return a script dict
    # ------------------------------------------------------------------

    def get_script(self, user_message: str) -> dict:
        """
        Send user_message to the chat and return the script as a dict.

        The returned dict follows the ReelMaker script format:
            { "script": { "1": ["CharName", "Dialogue"], ... } }
        """
        if self.chat is None:
            raise RuntimeError("Chat not initialised. Call init_chat() first.")

        response = self.chat.send_message(user_message)
        raw = response.text.strip()

        # Strip markdown code fences if the model wraps the JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"[LLMClient] Model returned non-JSON response:\n{raw}") from e

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_prompt(self) -> str:
        if not os.path.isfile(self.prompt_file):
            raise FileNotFoundError(
                f"Prompt file not found: {self.prompt_file}\n"
                "Create 'prompt.txt' in the project root."
            )
        with open(self.prompt_file, "r", encoding="utf-8") as f:
            return f.read().strip()
