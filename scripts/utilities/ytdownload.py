import os
import yt_dlp

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BG_VIDEO_DIR = os.path.join(_PROJECT_ROOT, "bgVideo")


def download_bg_video(url: str, filename: str = None) -> str:
    """
    Download a YouTube video into bgVideo/.

    Args:
        url:      YouTube video URL
        filename: output name without extension (defaults to video title)

    Returns:
        Full path to the saved mp4 file.
    """
    os.makedirs(BG_VIDEO_DIR, exist_ok=True)

    outtmpl = (
        os.path.join(BG_VIDEO_DIR, f"{filename}.%(ext)s")
        if filename
        else os.path.join(BG_VIDEO_DIR, "%(title)s.%(ext)s")
    )

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        saved = ydl.prepare_filename(info).rsplit(".", 1)[0] + ".mp4"

    print(f"[ytdownload] Saved -> {saved}")
    return saved


if __name__ == "__main__":
    download_bg_video(
        url="https://www.youtube.com/shorts/LofyMQts7hY",
        filename="bg1",
    )
