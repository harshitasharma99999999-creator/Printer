"""Create a branded 1080x1920 Reel/Short and optionally request a HeyGen presenter."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

from grand_forno_common import ROOT, read_json

FFMPEG = os.getenv("FFMPEG_BINARY") or shutil.which("ffmpeg")
FFPROBE = os.getenv("FFPROBE_BINARY") or shutil.which("ffprobe")


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def media_duration(path: Path) -> float:
    if FFPROBE:
        result = subprocess.run(
            [
                FFPROBE,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())
    if not FFMPEG:
        raise RuntimeError("FFmpeg is required")
    result = subprocess.run(
        [
            FFMPEG,
            "-v",
            "info",
            "-i",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    match = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", result.stderr)
    if not match:
        raise RuntimeError(f"Could not determine media duration for {path}")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def upload_heygen_audio(audio_path: Path) -> str:
    with audio_path.open("rb") as handle:
        response = requests.post(
            "https://upload.heygen.com/v1/asset",
            headers={"X-Api-Key": os.environ["AVATAR_API_KEY"], "Content-Type": "audio/mpeg"},
            data=handle,
            timeout=180,
        )
    response.raise_for_status()
    payload = response.json()
    asset_id = payload.get("data", {}).get("id")
    if not asset_id:
        raise RuntimeError(f"HeyGen audio upload returned no asset id: {payload}")
    return asset_id


def request_heygen_presenter(audio_path: Path, output: Path) -> None:
    avatar_id = os.environ["AVATAR_ID"]
    audio_asset_id = upload_heygen_audio(audio_path)
    response = requests.post(
        "https://api.heygen.com/v2/video/generate",
        headers={"X-Api-Key": os.environ["AVATAR_API_KEY"], "Content-Type": "application/json"},
        json={
            "video_inputs": [
                {
                    "character": {
                        "type": "avatar",
                        "avatar_id": avatar_id,
                        "avatar_style": "normal",
                    },
                    "voice": {"type": "audio", "audio_asset_id": audio_asset_id},
                    "background": {"type": "color", "value": "#FFF6E8"},
                }
            ],
            "dimension": {"width": 1080, "height": 1920},
            "aspect_ratio": "9:16",
            "caption": False,
        },
        timeout=90,
    )
    response.raise_for_status()
    video_id = response.json().get("data", {}).get("video_id")
    if not video_id:
        raise RuntimeError(f"HeyGen returned no video id: {response.text}")

    deadline = time.monotonic() + 15 * 60
    while time.monotonic() < deadline:
        status_response = requests.get(
            "https://api.heygen.com/v1/video_status.get",
            params={"video_id": video_id},
            headers={"X-Api-Key": os.environ["AVATAR_API_KEY"]},
            timeout=60,
        )
        status_response.raise_for_status()
        data = status_response.json().get("data", {})
        if data.get("status") == "completed":
            video_url = data.get("video_url")
            if not video_url:
                raise RuntimeError("HeyGen completed without a video URL")
            download = requests.get(video_url, timeout=180)
            download.raise_for_status()
            output.write_bytes(download.content)
            return
        if data.get("status") == "failed":
            raise RuntimeError(f"HeyGen generation failed: {data.get('error')}")
        time.sleep(10)
    raise TimeoutError("HeyGen presenter generation exceeded 15 minutes")


def srt_timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def write_subtitles(script: str, duration: float, output: Path) -> None:
    words = script.split()
    chunks: list[str] = []
    for index in range(0, len(words), 7):
        chunks.append(" ".join(words[index : index + 7]))
    usable = max(1.0, duration - 5.2)
    total_words = max(1, len(words))
    cursor = 0.0
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        share = len(chunk.split()) / total_words
        end = min(usable, cursor + usable * share)
        blocks.append(
            f"{index}\n{srt_timestamp(cursor)} --> {srt_timestamp(end)}\n{chunk}\n"
        )
        cursor = end
    output.write_text("\n".join(blocks), encoding="utf-8")


def ffmpeg_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:")


def find_product_image(item_id: str) -> Path:
    image_dir = ROOT / "assets" / "product_images"
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = image_dir / f"{item_id}{suffix}"
        if candidate.exists():
            return candidate
    default = image_dir / "default-fruit-bowl.png"
    if default.exists():
        return default
    return ROOT / "assets" / "logo.png"


def render(
    content_path: Path,
    audio_path: Path,
    output: Path,
    allow_fallback: bool,
) -> dict[str, Any]:
    if not FFMPEG:
        raise RuntimeError("FFmpeg is required")
    content = read_json(content_path)
    work_dir = output.parent
    work_dir.mkdir(parents=True, exist_ok=True)
    presenter = work_dir / "presenter.mp4"
    avatar_status = "generated"
    if os.getenv("AVATAR_API_KEY") and os.getenv("AVATAR_ID"):
        try:
            request_heygen_presenter(audio_path, presenter)
        except Exception as error:
            if not allow_fallback:
                raise
            avatar_status = f"fallback ({type(error).__name__})"
    elif allow_fallback:
        avatar_status = "fallback (avatar credentials absent)"
    else:
        raise RuntimeError("AVATAR_API_KEY and AVATAR_ID are required")

    duration = min(35.0, max(20.0, media_duration(audio_path) + 4.5))
    subtitle_path = work_dir / "subtitles.srt"
    write_subtitles(content["script"], duration, subtitle_path)

    text_dir = work_dir / "overlay_text"
    text_dir.mkdir(exist_ok=True)
    item_text = text_dir / "item.txt"
    benefits_text = text_dir / "benefits.txt"
    cta_text = text_dir / "cta.txt"
    links_text = text_dir / "links.txt"
    item_text.write_text(content["item"]["name"], encoding="utf-8")
    benefits_text.write_text(
        "\n".join(f"• {value}" for value in content["benefit_overlays"]),
        encoding="utf-8",
    )
    cta_text.write_text("Order now on Zomato & Swiggy", encoding="utf-8")
    links_text.write_text(
        "Zomato: zomato.onelink.me/xqzv/w36rgxfb\n"
        "Swiggy: swiggy.com/menu/1308871",
        encoding="utf-8",
    )

    logo = ROOT / "assets" / "logo.png"
    if not logo.exists():
        raise RuntimeError("assets/logo.png is required")
    product = find_product_image(content["item"]["id"])
    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if not font.exists():
        font = ROOT / "fonts" / "bold_font.ttf"

    command = [FFMPEG, "-y"]
    if presenter.exists():
        command += ["-i", str(presenter)]
    else:
        command += ["-loop", "1", "-i", str(product)]
    command += ["-i", str(audio_path), "-i", str(logo), "-loop", "1", "-i", str(product)]

    end_start = max(0.0, duration - 5.0)
    filter_graph = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,setsar=1,tpad=stop_mode=clone:stop_duration=12[base];"
        "[2:v]scale=190:-1[logo];"
        "[3:v]scale=430:430:force_original_aspect_ratio=decrease,"
        "pad=430:430:(ow-iw)/2:(oh-ih)/2:color=white[product];"
        "[base]drawbox=x=0:y=0:w=iw:h=285:color=black@0.42:t=fill,"
        f"drawtext=fontfile='{ffmpeg_path(font)}':text='Grand Forno':"
        "fontcolor=white:fontsize=62:x=(w-text_w)/2:y=145,"
        f"drawtext=fontfile='{ffmpeg_path(font)}':textfile='{ffmpeg_path(item_text)}':"
        "fontcolor=#FFE27A:fontsize=54:x=(w-text_w)/2:y=218[branded];"
        "[branded][logo]overlay=55:45[withlogo];"
        "[withlogo][product]overlay=W-w-55:670:enable='between(t,2.5,12.5)'[withproduct];"
        f"[withproduct]drawtext=fontfile='{ffmpeg_path(font)}':"
        f"textfile='{ffmpeg_path(benefits_text)}':fontcolor=white:fontsize=43:"
        "line_spacing=16:x=65:y=1180:box=1:boxcolor=black@0.48:boxborderw=24:"
        "enable='between(t,3,15)',"
        f"subtitles='{ffmpeg_path(subtitle_path)}':"
        "force_style='FontName=DejaVu Sans,FontSize=8,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=3,Outline=1,Shadow=0,MarginV=36,Alignment=2',"
        f"drawtext=fontfile='{ffmpeg_path(font)}':textfile='{ffmpeg_path(cta_text)}':"
        f"fontcolor=white:fontsize=48:x=(w-text_w)/2:y=1375:"
        f"box=1:boxcolor=#D84315@0.92:boxborderw=24:enable='gte(t,{end_start - 3:.2f})',"
        f"drawbox=x=0:y=0:w=iw:h=ih:color=#173B2A:t=fill:enable='gte(t,{end_start:.2f})',"
        f"drawtext=fontfile='{ffmpeg_path(font)}':text='Grand Forno':"
        f"fontcolor=#FFE27A:fontsize=88:x=(w-text_w)/2:y=570:enable='gte(t,{end_start:.2f})',"
        f"drawtext=fontfile='{ffmpeg_path(font)}':text='Order now on Zomato & Swiggy':"
        f"fontcolor=white:fontsize=45:x=(w-text_w)/2:y=770:enable='gte(t,{end_start:.2f})',"
        f"drawtext=fontfile='{ffmpeg_path(font)}':textfile='{ffmpeg_path(links_text)}':"
        f"fontcolor=white:fontsize=29:line_spacing=18:x=(w-text_w)/2:y=900:"
        f"enable='gte(t,{end_start:.2f})'[v]"
    )
    command += [
        "-filter_complex",
        filter_graph,
        "-map",
        "[v]",
        "-map",
        "1:a:0",
        "-af",
        "apad",
        "-t",
        f"{duration:.3f}",
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-movflags",
        "+faststart",
        str(output),
    ]
    run(command)
    return {"duration_seconds": round(duration, 2), "avatar_status": avatar_status}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-fallback", action="store_true")
    args = parser.parse_args()
    metadata = render(
        Path(args.content), Path(args.audio), Path(args.output), args.allow_fallback
    )
    print(metadata)


if __name__ == "__main__":
    main()
