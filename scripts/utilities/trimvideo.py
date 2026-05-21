import os
import subprocess

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def trim_front(input_path: str, seconds: float = 1.0, output_path: str = None) -> str:
    """
    Trim `seconds` from the front of a video using FFmpeg (no re-encode).

    Args:
        input_path:  path to source video
        seconds:     how many seconds to cut from the start
        output_path: where to save result (defaults to <name>_trimmed.<ext>)

    Returns:
        Path to the trimmed file.
    """
    if output_path is None:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_trimmed{ext}"

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-ss", str(seconds),
            "-i", input_path,
            "-c", "copy",
            output_path,
        ],
        check=True,
    )
    print(f"[trimvideo] Trimmed {seconds}s from front -> {output_path}")
    return output_path


if __name__ == "__main__":
    trim_front(
        input_path=os.path.join(_PROJECT_ROOT, "bgVideo", "bg1.mp4"),
        seconds=1.0,
    )
