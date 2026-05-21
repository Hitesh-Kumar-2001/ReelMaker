import os
import sys
from PIL import Image

SUPPORTED = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def mirror_image(src: str, dst: str = None) -> str:
    """
    Horizontally flip an image (mirror from right boundary).

    Args:
        src: path to the source image
        dst: output path (default: overwrites src)

    Returns:
        Path to the saved mirrored image.
    """
    img = Image.open(src)
    mirrored = img.transpose(Image.FLIP_LEFT_RIGHT)
    out = dst or src
    mirrored.save(out)
    print(f"[imgflip] Mirrored -> {out}")
    return out


def mirror_folder(folder: str, dst_folder: str = None) -> list:
    """
    Mirror all supported images in a folder.

    Args:
        folder:     source folder
        dst_folder: output folder (default: overwrites originals)

    Returns:
        List of output paths.
    """
    if dst_folder:
        os.makedirs(dst_folder, exist_ok=True)

    results = []
    for fname in sorted(os.listdir(folder)):
        if os.path.splitext(fname)[1].lower() not in SUPPORTED:
            continue
        src = os.path.join(folder, fname)
        dst = os.path.join(dst_folder, fname) if dst_folder else None
        results.append(mirror_image(src, dst))

    print(f"[imgflip] Done. {len(results)} image(s) processed.")
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python imgflip.py <image_file>              # mirror single image (overwrites)")
        print("  python imgflip.py <image_file> <out_file>   # mirror to new file")
        print("  python imgflip.py <folder>                  # mirror all images in folder")
        print("  python imgflip.py <folder> <out_folder>     # mirror folder to new folder")
        sys.exit(1)

    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None

    if os.path.isdir(src):
        mirror_folder(src, dst)
    else:
        mirror_image(src, dst)
