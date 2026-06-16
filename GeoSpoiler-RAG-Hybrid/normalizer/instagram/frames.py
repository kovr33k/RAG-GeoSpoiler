"""Frame extraction, deduplication, and filtering for Instagram Reels."""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("geospoiler.normalizer.instagram")

def _extract_frames(
    video_path: Path, frames_dir: Path, interval: float
) -> list[Path]:
    """Extract frames from video at given interval."""
    pattern = str(frames_dir / "frame_%04d.jpg")
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(video_path),
                "-vf", f"fps=1/{interval}",
                "-q:v", "3",
                pattern,
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"ffmpeg frame extraction timeout for {video_path}")
        return []
    except FileNotFoundError:
        logger.error("ffmpeg not found")
        return []

    return sorted(frames_dir.glob("frame_*.jpg"))

def _dedup_frames(frames: list[Path], threshold: int = 5) -> list[Path]:
    """
    Remove near-duplicate frames using perceptual hash (phash).
    Keeps a frame only if its Hamming distance to the previous kept frame > threshold.
    """
    if not frames:
        return []

    unique = [frames[0]]
    prev_hash = _compute_phash(frames[0])
    if prev_hash is None:
        return frames  # Can't compute hashes, return all

    for frame_path in frames[1:]:
        current_hash = _compute_phash(frame_path)
        if current_hash is None:
            unique.append(frame_path)
            continue

        distance = _hamming_distance(prev_hash, current_hash)
        if distance > threshold:
            unique.append(frame_path)
            prev_hash = current_hash

    return unique

def _compute_phash(image_path: Path, hash_size: int = 8) -> int | None:
    """
    Compute a perceptual hash for an image.
    Resize to (hash_size+1)×hash_size, convert to grayscale,
    compute horizontal gradient, produce hash_size² bit hash.
    """
    try:
        from PIL import Image

        img = Image.open(image_path).convert("L").resize(
            (hash_size + 1, hash_size), Image.LANCZOS
        )
        pixels = list(img.getdata()) if not hasattr(img, 'get_flattened_data') else list(img.get_flattened_data())
        width = hash_size + 1

        bits = []
        for y in range(hash_size):
            for x in range(hash_size):
                bits.append(1 if pixels[y * width + x] > pixels[y * width + x + 1] else 0)

        return int("".join(str(b) for b in bits), 2)

    except Exception as e:
        logger.debug(f"phash computation failed for {image_path}: {e}")
        return None

def _hamming_distance(h1: int, h2: int) -> int:
    """Compute Hamming distance between two integer hashes."""
    return bin(h1 ^ h2).count("1")

def _filter_empty_frames(frames: list[Path], edge_threshold: float = 0.10) -> list[Path]:
    """
    Filter out frames with low edge density (blank screens, talking heads without text).
    Uses Pillow-based Laplacian approximation.
    """
    if not frames:
        return []

    content_frames = []
    for frame_path in frames:
        density = _compute_edge_density(frame_path)
        if density is None or density >= edge_threshold:
            content_frames.append(frame_path)

    return content_frames if content_frames else frames[:1]  # Keep at least 1 frame

def _compute_edge_density(image_path: Path) -> float | None:
    """
    Estimate edge density using Pillow (no OpenCV needed).
    Applies a Laplacian-like kernel and measures fraction of "edge" pixels.
    """
    try:
        from PIL import Image, ImageFilter

        img = Image.open(image_path).convert("L").resize((160, 120), Image.LANCZOS)

        # Apply edge-finding filter
        edges = img.filter(ImageFilter.FIND_EDGES)

        pixels = list(edges.getdata()) if not hasattr(edges, 'get_flattened_data') else list(edges.get_flattened_data())
        total = len(pixels)
        edge_pixels = sum(1 for p in pixels if p > 30)

        return edge_pixels / total if total > 0 else 0.0

    except Exception as e:
        logger.debug(f"Edge density computation failed for {image_path}: {e}")
        return None
