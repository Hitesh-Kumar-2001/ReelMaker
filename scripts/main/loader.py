import os
import json

AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".aac", ".flac", ".m4a"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _first_file(folder, extensions):
    for f in sorted(os.listdir(folder)):
        if os.path.splitext(f)[1].lower() in extensions:
            return os.path.join(folder, f)
    return None


def _all_files(folder, extensions):
    return sorted(
        [os.path.join(folder, f) for f in os.listdir(folder)
         if os.path.splitext(f)[1].lower() in extensions],
        key=lambda p: os.path.splitext(os.path.basename(p))[0].zfill(10)
    )


def _load_character_photos(characters_dir, char_names):
    photos = {}
    for name in char_names:
        char_dir = os.path.join(characters_dir, name)
        if not os.path.isdir(char_dir):
            raise FileNotFoundError(f"Character folder not found: {char_dir}")
        files = _all_files(char_dir, IMAGE_EXTENSIONS)
        if not files:
            raise FileNotFoundError(f"No images found for character '{name}' in {char_dir}")
        photos[name] = files
    return photos


def load_post(post_number):
    """
    Load all assets for a given post number.

    Returns a dict:
    {
        "post_number": int,
        "bg_video": str,                        # path to background video
        "script": {                             # ordered list of lines
            "1": {"char": str, "dialogue": str, "audio": str},
            ...
        },
        "characters": {                         # char name -> list of photo paths
            "CharName": ["path/photo1.png", ...]
        }
    }
    """
    post_number = int(post_number)

    bg_dir      = os.path.join(BASE_DIR, "bgVideo")
    post_dir    = os.path.join(BASE_DIR, "posts", str(post_number))
    audio_dir   = os.path.join(post_dir, "audioFiles")
    script_path = os.path.join(post_dir, "script.json")
    chars_dir   = os.path.join(BASE_DIR, "Characters")

    for folder in [bg_dir, post_dir, audio_dir, chars_dir]:
        os.makedirs(folder, exist_ok=True)

    bg_video = _first_file(bg_dir, VIDEO_EXTENSIONS)
    if bg_video is None:
        raise FileNotFoundError(f"No video file found in {bg_dir}")

    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"script.json not found at {script_path}")
    with open(script_path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    raw_script = raw.get("script", {})

    audio_files = {}
    for fpath in _all_files(audio_dir, AUDIO_EXTENSIONS):
        key = os.path.splitext(os.path.basename(fpath))[0]
        audio_files[key] = fpath

    script = {}
    for line_num, entry in sorted(raw_script.items(), key=lambda x: int(x[0])):
        char_name = entry[0]
        dialogue  = entry[1]
        subtitle  = entry[2] if len(entry) > 2 else dialogue

        audio_path = audio_files.get(str(line_num))
        if audio_path is None:
            raise FileNotFoundError(
                f"Audio file for line {line_num} not found in {audio_dir}"
            )
        script[str(line_num)] = {
            "char":     char_name,
            "dialogue": dialogue,
            "subtitle": subtitle,
            "audio":    audio_path,
        }

    char_names = {entry["char"] for entry in script.values()}
    characters = _load_character_photos(chars_dir, char_names)

    return {
        "post_number": post_number,
        "bg_video":    bg_video,
        "script":      script,
        "characters":  characters,
    }


if __name__ == "__main__":
    import sys
    import pprint
    if len(sys.argv) != 2:
        print("Usage: python loader.py <post_number>")
        sys.exit(1)
    pprint.pprint(load_post(sys.argv[1]))
