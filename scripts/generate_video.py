"""Create a branded 1080x1920 Reel/Short and optionally request a HeyGen presenter."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import requests

from fresh_hvn_cinematic_assets import ensure_cinematic_assets, style_slug
from grand_forno_common import BRAND_NAME, DIRECT_ORDER_CONTACT, ROOT, read_json

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
            # HeyGen's free API tier is limited to 720p. The final FFmpeg
            # composition still upscales and exports at the required 1080x1920.
            "dimension": {"width": 720, "height": 1280},
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


def wrap_label(value: str, max_chars: int = 22) -> str:
    words = value.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join([*current, word]).strip()
        if current and len(candidate) > max_chars:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines[:2])


def ffmpeg_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace(":", r"\:")


def find_product_image(item_id: str, allow_fallback: bool = False) -> Path:
    image_dir = ROOT / "assets" / "product_images"
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = image_dir / f"{item_id}{suffix}"
        if candidate.exists():
            return candidate
    if not allow_fallback:
        raise RuntimeError(
            f"Missing item-specific product visual for {item_id}. "
            f"Add assets/product_images/{item_id}.png or .jpg before publishing."
        )
    default = image_dir / "fresh-hvn-default-can.png"
    if default.exists():
        return default
    return ROOT / "assets" / "logo.png"


def find_background_music() -> Path | None:
    configured = os.getenv("BACKGROUND_MUSIC_PATH", "").strip()
    candidates: list[Path] = []
    if configured:
        candidates.append((ROOT / configured).resolve() if not Path(configured).is_absolute() else Path(configured))
    music_dir = ROOT / "assets" / "music"
    approved_files = approved_music_files(music_dir)
    for suffix in ("*.mp3", "*.m4a", "*.wav", "*.aac", "*.ogg"):
        candidates.extend(sorted(music_dir.glob(suffix)))
    for candidate in candidates:
        resolved = candidate.resolve()
        if approved_files and resolved.name not in approved_files:
            continue
        if resolved.exists() and resolved.is_file() and resolved.stat().st_size > 0:
            return candidate
    return None


def approved_music_files(music_dir: Path) -> set[str]:
    manifest = music_dir / "trending_songs.json"
    if not manifest.exists():
        return set()
    with manifest.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return {
        str(track.get("file", "")).strip()
        for track in data.get("tracks", [])
        if str(track.get("status", "")).strip().lower() == "approved"
        and str(track.get("language", "")).strip().lower() == "english"
        and str(track.get("file", "")).strip()
    }


def render(
    content_path: Path,
    audio_path: Path | None,
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
    avatar_mode = os.getenv("AVATAR_MODE", "auto").strip().lower()
    music_only = audio_path is None
    if music_only:
        avatar_status = "music-only (voiceover disabled)"
    elif avatar_mode == "visual":
        avatar_status = "fallback (visual mode configured)"
    elif os.getenv("AVATAR_API_KEY") and os.getenv("AVATAR_ID"):
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

    duration = (
        float(os.getenv("MUSIC_ONLY_DURATION_SECONDS", "28"))
        if music_only
        else min(35.0, max(20.0, media_duration(audio_path) + 4.5))
    )
    subtitle_path = work_dir / "subtitles.srt"
    write_subtitles(content["script"], duration, subtitle_path)

    text_dir = work_dir / "overlay_text"
    text_dir.mkdir(exist_ok=True)
    item_text = text_dir / "item.txt"
    benefits_text = text_dir / "benefits.txt"
    cta_text = text_dir / "cta.txt"
    links_text = text_dir / "links.txt"
    hook_text = text_dir / "hook.txt"
    price_text = text_dir / "price.txt"
    style_text = text_dir / "style.txt"
    item_text.write_text(wrap_label(content["item"]["name"]), encoding="utf-8")
    benefits_text.write_text(
        "\n".join(f"- {value}" for value in content["benefit_overlays"]),
        encoding="utf-8",
    )
    cta_text.write_text(f"Order on {DIRECT_ORDER_CONTACT}", encoding="utf-8")
    hook_text.write_text(str(content.get("cinematic_style", "Fresh HVN")).upper(), encoding="utf-8")
    price_text.write_text(
        f"{content['item']['price']} | Same menu price as Zomato",
        encoding="utf-8",
    )
    style_text.write_text(str(content.get("visual_direction", "Cinematic chilled beverage ad")), encoding="utf-8")
    links_text.write_text(
        f"Same menu price as Zomato\n"
        f"Contact: {DIRECT_ORDER_CONTACT}",
        encoding="utf-8",
    )

    logo = ROOT / "assets" / "logo.png"
    if not logo.exists():
        raise RuntimeError("assets/logo.png is required")
    product = find_product_image(content["item"]["id"], allow_fallback=allow_fallback)
    cinematic_assets = ensure_cinematic_assets()
    campaign_slug = style_slug(str(content.get("cinematic_style", "")))
    background = cinematic_assets["backgrounds"][campaign_slug]  # type: ignore[index]
    can_overlay = cinematic_assets["can"]  # type: ignore[index]
    music = find_background_music()
    if music_only and not music:
        raise RuntimeError(
            "An approved English trending-style song is required because voiceover is disabled. "
            "Add the licensed file to assets/music and list it in assets/music/trending_songs.json."
        )
    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if not font.exists():
        font = ROOT / "fonts" / "bold_font.ttf"

    command = [FFMPEG, "-y", "-loop", "1", "-i", str(background)]
    next_input = 1
    narration_input = None
    if not music_only:
        command += ["-i", str(audio_path)]
        narration_input = next_input
        next_input += 1
    command += ["-i", str(logo)]
    logo_input = next_input
    next_input += 1
    command += ["-loop", "1", "-i", str(can_overlay)]
    can_input = next_input
    next_input += 1
    music_input = next_input
    if music:
        command += ["-stream_loop", "-1", "-i", str(music)]

    end_start = max(0.0, duration - 5.0)
    can_y = "520+16*sin(t*2.1)"
    can_x = "W-w-45+10*sin(t*1.2)"
    if campaign_slug == "ice-drop":
        can_y = "if(lt(t,1.35),-h+((520+h)/1.35)*t,520+18*sin(t*2.4))"
    elif campaign_slug == "gym-recovery":
        can_y = "610+10*sin(t*1.7)"
    elif campaign_slug == "fruit-vortex":
        can_x = "W-w-55+28*sin(t*1.7)"
        can_y = "505+22*cos(t*1.5)"

    subtitle_filter = ""
    if not music_only:
        subtitle_filter = (
            f"subtitles='{ffmpeg_path(subtitle_path)}':"
            "force_style='FontName=DejaVu Sans,FontSize=8,PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,BorderStyle=3,Outline=1,Shadow=0,MarginV=36,Alignment=2',"
        )

    filter_graph = (
        "[0:v]scale=1188:2112:force_original_aspect_ratio=increase,"
        "crop=1080:1920:x='54+18*sin(t*0.7)':y='96+22*cos(t*0.5)',"
        "setsar=1,eq=saturation=1.2:contrast=1.08:brightness=0.01,"
        "drawbox=x=0:y=0:w=iw:h=410:color=black@0.36:t=fill,"
        "drawbox=x=0:y=1550:w=iw:h=370:color=black@0.42:t=fill,"
        f"drawtext=fontfile='{ffmpeg_path(font)}':textfile='{ffmpeg_path(hook_text)}':"
        "fontcolor=#FFE27A:fontsize=45:x=58:y=112:"
        "box=1:boxcolor=black@0.36:boxborderw=18,"
        f"drawtext=fontfile='{ffmpeg_path(font)}':textfile='{ffmpeg_path(item_text)}':"
        "fontcolor=white:fontsize=42:line_spacing=8:x=58:y=190,"
        f"drawtext=fontfile='{ffmpeg_path(font)}':textfile='{ffmpeg_path(price_text)}':"
        "fontcolor=#DFF8E6:fontsize=30:x=58:y=350[base];"
        f"[{logo_input}:v]scale=118:-1[logo];"
        f"[{can_input}:v]scale=500:-1,format=rgba[can];"
        "[base][logo]overlay=W-w-50:54[withlogo];"
        f"[withlogo][can]overlay=x='{can_x}':y='{can_y}':enable='lt(t,{end_start:.2f})'[withcan];"
        f"[withcan]drawtext=fontfile='{ffmpeg_path(font)}':"
        f"textfile='{ffmpeg_path(benefits_text)}':fontcolor=white:fontsize=39:"
        "line_spacing=17:x=58:y=1235:box=1:boxcolor=black@0.46:boxborderw=22:"
        "enable='between(t,4,15)',"
        f"{subtitle_filter}"
        f"drawtext=fontfile='{ffmpeg_path(font)}':textfile='{ffmpeg_path(cta_text)}':"
        f"fontcolor=white:fontsize=54:x=(w-text_w)/2:y=1465:"
        f"box=1:boxcolor=#D84315@0.94:boxborderw=25:enable='between(t,13,{end_start:.2f})',"
        f"drawbox=x=0:y=0:w=iw:h=ih:color=#102E25:t=fill:enable='gte(t,{end_start:.2f})',"
        f"drawtext=fontfile='{ffmpeg_path(font)}':text='{BRAND_NAME}':"
        f"fontcolor=#FFE27A:fontsize=96:x=(w-text_w)/2:y=520:enable='gte(t,{end_start:.2f})',"
        f"drawtext=fontfile='{ffmpeg_path(font)}':textfile='{ffmpeg_path(item_text)}':"
        f"fontcolor=white:fontsize=38:line_spacing=10:x=(w-text_w)/2:y=675:enable='gte(t,{end_start:.2f})',"
        f"drawtext=fontfile='{ffmpeg_path(font)}':text='Order on {DIRECT_ORDER_CONTACT}':"
        f"fontcolor=white:fontsize=46:x=(w-text_w)/2:y=895:enable='gte(t,{end_start:.2f})',"
        f"drawtext=fontfile='{ffmpeg_path(font)}':textfile='{ffmpeg_path(links_text)}':"
        f"fontcolor=#DFF8E6:fontsize=31:line_spacing=18:x=(w-text_w)/2:y=1035:"
        f"enable='gte(t,{end_start:.2f})'[v]"
    )
    if music:
        music_fade_out = max(0.0, duration - 1.5)
        filter_graph += (
            f";[{music_input}:a]atrim=0:{duration:.3f},asetpts=PTS-STARTPTS,"
            f"volume={os.getenv('BACKGROUND_MUSIC_VOLUME', '0.85' if music_only else '0.12')},"
            f"afade=t=in:st=0:d=1.0,"
            f"afade=t=out:st={music_fade_out:.3f}:d=1.5[music]"
        )
        if music_only:
            filter_graph += ";[music]apad[a]"
        else:
            filter_graph += f";[{narration_input}:a]volume=1.0[narration];[narration][music]amix=inputs=2:duration=first:dropout_transition=0,apad[a]"
        audio_options = ["-map", "[a]"]
    else:
        if narration_input is None:
            raise RuntimeError("Background music is required for music-only Fresh HVN posts.")
        audio_options = ["-map", f"{narration_input}:a:0", "-af", "apad"]
    command += [
        "-filter_complex",
        filter_graph,
        "-map",
        "[v]",
        *audio_options,
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
    return {
        "duration_seconds": round(duration, 2),
        "avatar_status": avatar_status,
        "product_visual": str(product.relative_to(ROOT)),
        "background_music": str(music.relative_to(ROOT)) if music else None,
        "voiceover": "disabled" if music_only else "enabled",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", required=True)
    parser.add_argument("--audio", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--allow-fallback", action="store_true")
    args = parser.parse_args()
    audio = None if args.audio.strip().lower() in {"none", "music-only", "disabled"} else Path(args.audio)
    metadata = render(Path(args.content), audio, Path(args.output), args.allow_fallback)
    print(metadata)


if __name__ == "__main__":
    main()
