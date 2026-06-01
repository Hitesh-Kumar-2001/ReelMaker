import json
import os
import re
import subprocess
import tempfile

import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from scripts.main.MiniMaxClient import MiniMaxClient
from scripts.GoogleDrive import GoogleDriveService

load_dotenv(override=True)

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
PAUSE     = 0.5

SUBTITLE_FONT_PATHS = [
    r"C:\Windows\Fonts\calibrib.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\bahnschrift.ttf",
    r"C:\Windows\Fonts\NirmalaUI.ttf",
]
SUBTITLE_FONT_SIZE       = 75
SUBTITLE_WORDS_PER_CHUNK = 3
SUBTITLE_PAUSE_EXTRA     = 0.4   # extra seconds a chunk stays when '...' follows it

TARGET_HEIGHT = 1440             # upscale bg video to this height (2K portrait)

VOICE_MAP = {
    "Arvind Kejriwal": "kejriwal_clone",
    "Raghav Chadha":   "raghav_clone",
}


# ------------------------------------------------------------------
# Load characters.json — photo path + position config
# ------------------------------------------------------------------

def _load_char_config() -> dict:
    path = os.path.join(BASE_DIR, "characters.json")
    if not os.path.isfile(path):
        raise FileNotFoundError("characters.json not found in project root.")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_char_photo(char_name: str, char_config: dict) -> str:
    cfg    = char_config.get(char_name, {})
    folder = cfg.get("folder", char_name.lower().replace(" ", "_"))
    photo  = cfg.get("photo", "normal.png")
    path   = os.path.join(BASE_DIR, "Characters", folder, photo)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Photo not found: {path}")
    return path


def _resolve_position(position: str, char_w: int, char_h: int, W: int, H: int):
    y = H - char_h
    if position == "left":
        return (0, y)
    if position == "right":
        return (W - char_w, y)
    if position == "center":
        return ((W - char_w) // 2, y)
    try:
        px, py = map(int, position.split(","))
        return (px, py)
    except Exception:
        return (0, y)


# ------------------------------------------------------------------
# Subtitle helpers
# ------------------------------------------------------------------

def _get_subtitle_font(size: int = SUBTITLE_FONT_SIZE):
    for path in SUBTITLE_FONT_PATHS:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _split_subtitle_with_pauses(subtitle: str) -> list:
    """
    Returns [(chunk_text, pause_after), ...].
    Splits on '...' as pause markers; the last chunk before each '...' gets
    SUBTITLE_PAUSE_EXTRA extra display time so it stays up during the audio gap.
    """
    parts = re.split(r'\.\.\.', subtitle)
    result = []
    for i, part in enumerate(parts):
        is_last_part = (i == len(parts) - 1)
        clean = re.sub(r'[^\w\s,]', '', part).strip()
        clean = ' '.join(clean.split())
        if not clean:
            continue
        words = clean.split()
        n = SUBTITLE_WORDS_PER_CHUNK
        sub_chunks = [' '.join(words[j:j+n]) for j in range(0, len(words), n)]
        for k, chunk in enumerate(sub_chunks):
            has_pause = (k == len(sub_chunks) - 1) and not is_last_part
            result.append((chunk, has_pause))
    return result if result else [(subtitle, False)]


def _render_subtitle_frame(chunk: str, W: int, font) -> np.ndarray:
    padding    = 10
    stroke_w   = 2
    dummy      = Image.new("RGBA", (1, 1))
    bbox       = ImageDraw.Draw(dummy).textbbox(
        (0, 0), chunk, font=font, stroke_width=stroke_w
    )
    text_h = bbox[3] - bbox[1]
    img_h  = text_h + padding * 2

    shadow = Image.new("RGBA", (W, img_h), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text(
        (W // 2, padding), chunk, font=font,
        fill=(0, 0, 0, 180), anchor="mt",
        stroke_width=stroke_w, stroke_fill=(0, 0, 0, 180),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=2))

    img = shadow.copy()
    ImageDraw.Draw(img).text(
        (W // 2, padding), chunk, font=font,
        fill=(255, 255, 255, 255), anchor="mt",
        stroke_width=stroke_w, stroke_fill=(0, 0, 0, 220),
    )
    return np.array(img)


def _nvenc_available() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=5,
        )
        return "h264_nvenc" in result.stdout
    except Exception:
        return False


def _load_script(post_number: int) -> dict:
    path = os.path.join(BASE_DIR, "posts", str(post_number), "script.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"script.json not found at {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f).get("script", {})


# ------------------------------------------------------------------
# Step 1 — generate audio files
# ------------------------------------------------------------------

def generate_audio_for_post(post_number: int = 1):
    post_dir  = os.path.join(BASE_DIR, "posts", str(post_number))
    audio_dir = os.path.join(post_dir, "audioFiles")
    os.makedirs(audio_dir, exist_ok=True)

    script = _load_script(post_number)
    client = MiniMaxClient()

    for line_num in sorted(script.keys(), key=int):
        entry     = script[line_num]
        char_name = entry[0]
        dialogue  = entry[1]
        voice_id  = VOICE_MAP.get(char_name)
        if not voice_id:
            raise ValueError(f"No voice mapped for '{char_name}'. Add to VOICE_MAP.")

        out = os.path.join(audio_dir, f"{line_num}.mp3")
        client.set_voice(voice_id)
        client.text_to_speech(text=dialogue, output_path=out)
        print(f"[reelMaker] {line_num}/{len(script)} | {char_name} -> {out}")

    print(f"[reelMaker] Audio done. {len(script)} file(s) in {audio_dir}")


# ------------------------------------------------------------------
# Step 2 — compose the reel video
# ------------------------------------------------------------------

def generate_reel(post_number: int = 1, output_path: str = None):
    from moviepy import (
        VideoFileClip, AudioFileClip, ImageClip,
        CompositeVideoClip, concatenate_videoclips,
    )

    post_dir  = os.path.join(BASE_DIR, "posts", str(post_number))
    audio_dir = os.path.join(post_dir, "audioFiles")
    if output_path is None:
        output_path = os.path.join(post_dir, "reel.mp4")

    script      = _load_script(post_number)
    char_config = _load_char_config()

    bg_dir  = os.path.join(BASE_DIR, "bgVideo")
    bg_file = next(
        (os.path.join(bg_dir, f) for f in sorted(os.listdir(bg_dir))
         if os.path.splitext(f)[1].lower() in {".mp4", ".mov", ".avi", ".mkv"}),
        None,
    )
    if not bg_file:
        raise FileNotFoundError("No background video found in bgVideo/")

    bg_clip  = VideoFileClip(bg_file)
    W, H     = bg_clip.size
    bg_pos   = 0.0
    segments = []
    sub_font = _get_subtitle_font()

    for line_num in sorted(script.keys(), key=int):
        entry     = script[line_num]
        char_name = entry[0]
        dialogue  = entry[1]
        subtitle_raw = entry[2] if len(entry) > 2 else dialogue
        subtitle     = subtitle_raw[0] if isinstance(subtitle_raw, list) else subtitle_raw
        cfg       = char_config.get(char_name, {})

        audio_path = os.path.join(audio_dir, f"{line_num}.mp3")
        audio_clip = AudioFileClip(audio_path)
        audio_dur  = audio_clip.duration
        seg_dur    = audio_dur + PAUSE

        # Background slice
        if bg_pos + seg_dur > bg_clip.duration:
            bg_pos = 0.0
        bg_seg  = bg_clip.subclipped(bg_pos, bg_pos + seg_dur)
        bg_pos += seg_dur

        # Character photo
        size_pct = cfg.get("size_pct", 35)
        photo_h  = int(H * size_pct / 100)
        photo    = _get_char_photo(char_name, char_config)
        img_pil  = Image.open(photo)
        ratio    = photo_h / img_pil.height
        photo_w  = int(img_pil.width * ratio)

        pos = _resolve_position(cfg.get("position", "left"), photo_w, photo_h, W, H)

        char_img = (
            ImageClip(photo)
            .with_duration(seg_dur)
            .resized(height=photo_h)
            .with_position(pos)
        )

        # Timed subtitle chunks — pause-aware
        chunks_meta  = _split_subtitle_with_pauses(subtitle)
        n_pauses     = sum(1 for _, p in chunks_meta if p)
        pause_budget = min(n_pauses * SUBTITLE_PAUSE_EXTRA, audio_dur * 0.4)
        base_dur     = (audio_dur - pause_budget) / len(chunks_meta)
        sub_clips = []
        t = 0.0
        for chunk_text, has_pause in chunks_meta:
            dur   = base_dur + (SUBTITLE_PAUSE_EXTRA if has_pause else 0)
            frame = _render_subtitle_frame(chunk_text, W, sub_font)
            sub_clips.append(
                ImageClip(frame)
                .with_start(t)
                .with_duration(dur)
                .with_position((0, 400))
            )
            t += dur

        composite = CompositeVideoClip([bg_seg, char_img] + sub_clips)
        composite = composite.with_audio(audio_clip)
        segments.append(composite)

        print(f"[reelMaker] Segment {line_num}/{len(script)} | {char_name} ({audio_dur:.1f}s + {PAUSE}s pause) | {len(chunks_meta)} subtitle chunk(s)")

    print("[reelMaker] Rendering...")
    final = concatenate_videoclips(segments)
    scale_filter = f"scale=-2:{TARGET_HEIGHT}:flags=lanczos"
    if _nvenc_available():
        print("[reelMaker] GPU encoder detected — using h264_nvenc")
        codec  = "h264_nvenc"
        params = ["-vf", scale_filter, "-b:v", "0", "-cq", "18", "-preset", "p4", "-profile:v", "high"]
    else:
        print("[reelMaker] No GPU encoder — falling back to libx264")
        codec  = "libx264"
        params = ["-vf", scale_filter, "-crf", "18", "-preset", "slow"]
    final.write_videofile(
        output_path, fps=30, codec=codec, audio_codec="aac",
        temp_audiofile_path=tempfile.gettempdir(), logger="bar",
        ffmpeg_params=params,
    )
    bg_clip.close()
    print(f"[reelMaker] Reel saved -> {output_path}")
    return output_path


# ------------------------------------------------------------------
# Step 3 — run full pipeline from tempScript.json
# ------------------------------------------------------------------

TEMP_SCRIPT      = os.path.join(BASE_DIR, "scripts", "tempScript.json")
POSTS_DIR        = os.path.join(BASE_DIR, "posts")
GDRIVE_FOLDER_ID = "1O9keZ0tARDgIeTpoRsOm49Eu8EhsBwr8"


def _next_post_number() -> int:
    os.makedirs(POSTS_DIR, exist_ok=True)
    existing = [
        int(d) for d in os.listdir(POSTS_DIR)
        if os.path.isdir(os.path.join(POSTS_DIR, d)) and d.isdigit()
    ]
    return max(existing, default=0) + 1


def run_from_temp():
    import json

    if not os.path.isfile(TEMP_SCRIPT):
        raise FileNotFoundError(f"tempScript.json not found at {TEMP_SCRIPT}")

    with open(TEMP_SCRIPT, "r", encoding="utf-8") as f:
        script_data = json.load(f)

    post_number = _next_post_number()
    post_dir    = os.path.join(POSTS_DIR, str(post_number))
    os.makedirs(os.path.join(post_dir, "audioFiles"), exist_ok=True)

    dest = os.path.join(post_dir, "script.json")
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(script_data, f, ensure_ascii=False, indent=4)

    print(f"[reelMaker] Post {post_number} created -> {post_dir}")
    generate_audio_for_post(post_number)
    reel_path = generate_reel(post_number)
    print(f"[reelMaker] Done -> posts/{post_number}/reel.mp4")

    audio_dir = os.path.join(post_dir, "audioFiles")
    for f in os.listdir(audio_dir):
        os.remove(os.path.join(audio_dir, f))
    os.rmdir(audio_dir)
    print(f"[reelMaker] Audio files deleted")

    if GDRIVE_FOLDER_ID:
        print(f"[reelMaker] Uploading to Google Drive...")
        drive = GoogleDriveService(None)
        file_id = drive.upload_file(reel_path, GDRIVE_FOLDER_ID)
        print(f"[reelMaker] Uploaded -> Drive file ID: {file_id}")
    else:
        print("[reelMaker] GDRIVE_FOLDER_ID not set in .env — skipping upload")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    run_from_temp()
