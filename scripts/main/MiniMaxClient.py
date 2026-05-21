import json
import os
import requests

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
VOICES_JSON = os.path.join(_PROJECT_ROOT, "voiceAvailable.json")


class MiniMaxClient:
    BASE_URL = "https://api.minimax.io/v1"

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("MINIMAX_API_KEY")
        if not self.api_key:
            raise ValueError(
                "API key required. Pass api_key= or set the MINIMAX_API_KEY environment variable."
            )
        self.voice_id: str | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _auth(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def _json_headers(self):
        return {**self._auth(), "Content-Type": "application/json"}

    def _check(self, body: dict):
        status = body.get("base_resp", {})
        if status.get("status_code") != 0:
            raise RuntimeError(
                f"MiniMax API error {status.get('status_code')}: {status.get('status_msg')}"
            )

    # ------------------------------------------------------------------
    # set_voice — point to an already-cloned voice (no API call)
    # ------------------------------------------------------------------

    def set_voice(self, voice_id: str):
        """Set the active voice to an already-cloned voice_id. No API call."""
        self.voice_id = voice_id
        print(f"[MiniMaxClient] Voice set -> '{voice_id}'")

    # ------------------------------------------------------------------
    # clone_voice — one-time: upload audio + clone, then set as active
    # ------------------------------------------------------------------

    def clone_voice(
        self,
        audio_path: str,
        voice_id: str,
        model: str = "speech-02-hd",
        need_noise_reduction: bool = False,
        need_volume_normalization: bool = False,
    ):
        """Upload audio and clone it into a new voice. Run once per voice."""
        if not os.path.isfile(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # 1. Upload
        with open(audio_path, "rb") as f:
            resp = requests.post(
                f"{self.BASE_URL}/files/upload",
                headers=self._auth(),
                data={"purpose": "voice_clone"},
                files={"file": (os.path.basename(audio_path), f, "audio/mpeg")},
                timeout=120,
            )
        resp.raise_for_status()
        body = resp.json()
        self._check(body)
        file_id = body["file"]["file_id"]
        print(f"[MiniMaxClient] Uploaded '{os.path.basename(audio_path)}' -> file_id={file_id}")

        # 2. Clone
        clone_resp = requests.post(
            f"{self.BASE_URL}/voice_clone",
            headers=self._json_headers(),
            json={
                "file_id": file_id,
                "voice_id": voice_id,
                "model": model,
                "need_noise_reduction": need_noise_reduction,
                "need_volume_normalization": need_volume_normalization,
            },
            timeout=120,
        )
        clone_resp.raise_for_status()
        self._check(clone_resp.json())

        self.voice_id = voice_id
        print(f"[MiniMaxClient] Voice cloned -> '{voice_id}'")

    # ------------------------------------------------------------------
    # refresh_voice_list — fetch all voices from API, save voiceAvailable.json
    # ------------------------------------------------------------------

    def refresh_voice_list(self, output_path: str = VOICES_JSON) -> dict:
        """Fetch system + cloned voices from MiniMax and save to voiceAvailable.json."""
        resp = requests.post(
            f"{self.BASE_URL}/get_voice",
            headers=self._json_headers(),
            json={"voice_type": "all"},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()
        self._check(body)

        data = {
            "system":           body.get("system_voice", []),
            "voice_cloning":    body.get("voice_cloning_voice", []),
            "voice_generation": body.get("voice_generation_voice", []),
        }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        total = sum(len(v) for v in data.values())
        print(f"[MiniMaxClient] {total} voices saved -> {output_path}")
        return data

    # ------------------------------------------------------------------
    # text_to_speech — uses active voice (self.voice_id or voice_id arg)
    # ------------------------------------------------------------------

    def text_to_speech(
        self,
        text: str,
        output_path: str = "voice.mp3",
        voice_id: str = None,
        model: str = "speech-02-hd",
        speed: float = 1.0,
        vol: float = 1.0,
        pitch: int = 0,
    ) -> str:
        """Synthesise speech. Uses voice_id arg if given, else falls back to self.voice_id."""
        active_voice = voice_id or self.voice_id
        if not active_voice:
            raise RuntimeError("No voice set. Call set_voice() or clone_voice() first.")

        resp = requests.post(
            f"{self.BASE_URL}/t2a_v2",
            headers=self._json_headers(),
            json={
                "model": model,
                "text": text,
                "voice_setting": {
                    "voice_id": active_voice,
                    "speed": speed,
                    "vol": vol,
                    "pitch": pitch,
                },
                "audio_setting": {
                    "format": "mp3",
                    "sample_rate": 32000,
                    "bitrate": 128000,
                    "channel": 1,
                },
            },
            timeout=60,
        )
        resp.raise_for_status()
        body = resp.json()
        self._check(body)

        audio_bytes = bytes.fromhex(body["data"]["audio"])
        with open(output_path, "wb") as f:
            f.write(audio_bytes)

        print(f"[MiniMaxClient] Saved {len(audio_bytes):,} bytes -> {output_path}")
        return output_path
