import os
import re
import time
import json
import uuid
import base64
import requests

from io import BytesIO
from uuid import uuid4
from datetime import datetime
from typing import List

from PIL import Image, ImageDraw, ImageFont

from status import *
from config import (
    ROOT_DIR, get_verbose, get_imagemagick_path,
    get_nanobanana2_api_key, get_nanobanana2_api_base_url, get_nanobanana2_model,
    get_fonts_dir, get_font, get_threads, get_stt_provider,
    get_assemblyai_api_key, equalize_subtitles, get_affiliate_link,
    get_whisper_model, get_whisper_device, get_whisper_compute_type,
    get_is_for_kids,
)
from llm_provider import generate_text

LONG_FORM_NICHES = [
    "spirituality and consciousness",
    "motivation and success mindset",
    "dark psychology",
    "female psychology",
    "male psychology",
    "law of seduction",
    "stoicism and philosophy",
    "law of attraction",
]


class LongForm:
    """
    Full pipeline for 10-15 minute long-form YouTube videos.
    Niches: spirituality, motivation, psychology, seduction.
    Produces 1920x1080 video with AI images, TTS, subtitles, and SEO thumbnail.
    """

    def __init__(
        self,
        account_uuid: str,
        account_nickname: str,
        fp_profile_path: str,
        niche: str,
        language: str,
    ) -> None:
        self.account_uuid = account_uuid
        self.account_nickname = account_nickname
        self.fp_profile_path = fp_profile_path
        self.niche = niche
        self.language = language

        self.subject: str = ""
        self.script: str = ""
        self.metadata: dict = {}
        self.images: List[str] = []
        self.tts_path: str = ""
        self.video_path: str = ""
        self.thumbnail_path: str = ""

        os.environ["IMAGEMAGICK_BINARY"] = get_imagemagick_path()

    # ------------------------------------------------------------------
    # Step 1: Topic
    # ------------------------------------------------------------------

    def generate_topic(self) -> str:
        prompt = (
            f"You are the creator of 'YourInnerGuide' — a channel that reveals ultimate spiritual truths to help people shift their reality.\n"
            f"Generate ONE deeply meaningful long-form YouTube video topic (10-15 minutes) about {self.niche}.\n"
            f"The topic must feel like a life-changing revelation — as if the viewer's higher self is calling them to watch.\n"
            f"Examples:\n"
            f"'The Ultimate Truth About Who You Really Are — And Why You Forgot It'\n"
            f"'How To Shift Your Reality Using The Power You Were Born With'\n"
            f"'Everything You Believe About Reality Is Wrong — Here Is The Truth'\n"
            f"'The Consciousness Blueprint: How To Awaken And Create The Life You Were Meant To Live'\n"
            f"'You Are A Multidimensional Being — This Is How To Access Your True Power'\n"
            f"Return ONLY the topic, nothing else."
        )
        raw = generate_text(prompt).strip()
        # tinyllama often returns a paragraph — take only the first non-empty line
        self.subject = next(
            (l.strip().strip('"').strip("'") for l in raw.splitlines() if l.strip()),
            raw.split(".")[0].strip()
        )
        return self.subject

    # ------------------------------------------------------------------
    # Step 2: Script (section by section for small LLMs)
    # ------------------------------------------------------------------

    def generate_script(self) -> str:
        parts = []

        # Hook — SCROLL-STOPPING, commanding male narrator energy
        hook = generate_text(
            f"Write a 4-sentence opening for a spiritual long-form YouTube video about: {self.subject}.\n"
            f"You are 'YourInnerGuide' — a deeply wise spiritual teacher revealing ultimate truths about consciousness and reality.\n"
            f"Sentence 1: Open with a profound ultimate truth that makes the viewer feel they have been waiting to hear this their whole life.\n"
            f"Sentence 2: Tell them something about their true nature or the nature of reality that most people never discover.\n"
            f"Sentence 3: Make it deeply personal — speak directly to 'you' as if you are their own inner voice finally speaking.\n"
            f"Sentence 4: Tell them exactly what truth they will carry with them after watching this video.\n"
            f"Language: {self.language}. NO titles, NO markdown. Calm, wise, profound spoken words only.\n"
            f"Use YOU and YOUR constantly. Reveal truth — never preach or suggest."
        ).strip()
        parts.append(hook)

        # Section outline
        outline_raw = generate_text(
            f"List exactly 5 section titles for a 12-minute 'YourInnerGuide' style spiritual video about: {self.subject}.\n"
            f"Each section should guide the viewer deeper into the truth — from realizing something is wrong, to discovering the truth, to knowing how to shift their reality.\n"
            f"Style: profound, guiding, consciousness-expanding. Like chapters of an awakening journey.\n"
            f"Format: numbered list 1-5. No explanations."
        ).strip()
        section_titles = []
        for line in outline_raw.splitlines():
            m = re.match(r"^\d+[\.\)]\s*(.+)", line.strip())
            if m:
                section_titles.append(m.group(1).strip())
        if len(section_titles) < 5:
            section_titles = [
                "The Truth About Who You Really Are",
                "Why Your Reality Feels Stuck — And What Is Actually Happening",
                "The Hidden Mechanics Of Consciousness And Reality",
                "How To Shift Your Reality Starting Right Now",
                "The Life That Awaits You On The Other Side Of This Truth",
            ]

        # Each section body — powerful masculine narrator
        for title in section_titles[:5]:
            section = generate_text(
                f"Write 6 deeply guiding spoken sentences for the section '{title}' "
                f"in a 'YourInnerGuide' style video about: {self.subject}.\n"
                f"Tone: calm, wise, certain — like a spiritual teacher revealing truth that changes everything.\n"
                f"Guide the viewer deeper into understanding their true nature, consciousness, and how to shift their reality.\n"
                f"Each sentence must feel like a revelation — truth they have always known but never had words for.\n"
                f"Language: {self.language}. NO markdown, NO headers. Wise, calm, profound spoken words only.\n"
                f"Use YOU and YOUR constantly. Reveal — never preach or lecture."
            ).strip()
            parts.append(section)

        # CTA — strong and direct
        cta = generate_text(
            f"Write a 3-sentence powerful closing for a YouTube video about: {self.subject}.\n"
            f"Tone: commanding, direct — challenge the viewer to act.\n"
            f"Ask them to like, share their truth in the comments, and subscribe for more.\n"
            f"Language: {self.language}. Raw spoken words only."
        ).strip()
        parts.append(cta)

        raw = "\n\n".join(p for p in parts if p)
        self.script = self._clean_script(raw)
        return self.script

    @staticmethod
    def _clean_script(text: str) -> str:
        import re
        # Prefixes that indicate non-spoken content
        BAD_STARTS = (
            'cut to', 'narrator', 'voiceover', 'voice over', 'showing',
            'key takeaway', 'key takeaways', 'examples:', 'example:',
            'sentence ', 'video begins', 'closing music', 'music plays',
            'introductory', 'explanation', 'host:', 'speaker:', 'scene:',
            'description:', 'title:', 'subtitle:', 'section ', 'part ',
            'chapter ', 'here is', 'note:', 'disclaimer:', 'tags:',
            'hook:', 'cta:', 'outro:', 'intro:', 'thumbnail:',
            '---', '===', '***',
        )
        lines = text.splitlines()
        cleaned = []
        for line in lines:
            stripped = line.strip()
            low = stripped.lower()
            # Skip blank lines that create paragraph breaks (keep single blank lines later)
            if not stripped:
                cleaned.append("")
                continue
            # Skip lines that start with screenplay/stage-direction patterns
            if any(low.startswith(p) for p in BAD_STARTS):
                continue
            # Skip lines that are entirely inside brackets/parens (stage directions)
            if re.match(r'^[\[\(].*[\]\)]$', stripped):
                continue
            # Skip markdown headers
            if re.match(r'^#{1,4}\s', stripped):
                continue
            # Skip bullet points that look like a list (not narration)
            if re.match(r'^[-*•]\s', stripped) and len(stripped) < 120:
                continue
            # Skip numbered list items
            if re.match(r'^\d+[\.\)]\s', stripped):
                continue
            # Drop lines with >30% non-ASCII (foreign language blocks)
            non_ascii = sum(1 for c in stripped if ord(c) > 127)
            if len(stripped) > 10 and non_ascii / len(stripped) > 0.3:
                continue
            cleaned.append(line)
        # Collapse multiple blank lines into one
        result = re.sub(r'\n{3,}', '\n\n', "\n".join(cleaned))
        return result.strip()

    # ------------------------------------------------------------------
    # Step 3: SEO Metadata
    # ------------------------------------------------------------------

    def generate_metadata(self) -> dict:
        title = generate_text(
            f"Write a YouTube video title for: {self.subject}.\n"
            f"Make it SEO-optimized, emotional, and highly clickable. Under 70 characters.\n"
            f"Return ONLY the title, no quotes."
        ).strip().strip('"').strip("'")
        if len(title) > 100:
            title = title[:97] + "..."

        description = generate_text(
            f"Write a YouTube video description for a video titled '{title}' about: {self.subject}.\n"
            f"Include SEO keywords naturally. 150-200 words. No markdown.\n"
            f"End with: Subscribe for weekly insights."
        ).strip()

        niche_tag = "#" + re.sub(r"[^a-zA-Z0-9]", "", self.niche.title())
        description += f"\n\n{niche_tag} #Motivation #Psychology #SelfImprovement"

        affiliate = get_affiliate_link()
        if affiliate:
            description += f"\n\n🛒 Recommended:\n{affiliate}"

        self.metadata = {"title": title, "description": description}
        return self.metadata

    # ------------------------------------------------------------------
    # Step 4: Image prompts (16:9)
    # ------------------------------------------------------------------

    def generate_image_prompts(self) -> List[str]:
        raw = generate_text(
            f"Generate 8 CINEMATIC 16:9 image prompts for a dark psychological YouTube video about: {self.subject}.\n"
            f"Style: epic movie-quality, dark and dramatic, hyper-realistic, emotional power.\n"
            f"Use: lone figures in vast landscapes, dramatic chiaroscuro lighting, stormy skies,\n"
            f"extreme close-ups of eyes/hands, symbolic imagery, apocalyptic beauty.\n"
            f"Return as JSON array of 8 strings only. Example: [\"scene1\", \"scene2\"]"
        ).strip()
        m = re.search(r"\[.*?\]", raw, re.DOTALL)
        if m:
            try:
                prompts = json.loads(m.group(0))
                if isinstance(prompts, list) and prompts:
                    return [str(p) for p in prompts[:8]]
            except Exception:
                pass
        return [
            f"Cinematic dark dramatic scene representing {self.subject}, moody lighting, 4K",
            f"Silhouette of person in deep thought, {self.niche}, dramatic atmosphere",
            f"Abstract visualization of {self.niche}, dark aesthetic, professional",
            f"Mysterious atmospheric wide shot, emotional, {self.subject}",
            f"Dark cinematic scene, person in contemplation, powerful emotion",
            f"Dramatic lighting, symbolic imagery, {self.subject}",
            f"Abstract dark background, subtle symbolism, {self.niche}",
            f"Epic cinematic composition representing transformation, {self.subject}",
        ]

    # ------------------------------------------------------------------
    # Step 5: Generate images via Gemini (16:9)
    # ------------------------------------------------------------------

    def _generate_image_gemini(self, prompt: str, aspect: str = "16:9") -> str:
        api_key = get_nanobanana2_api_key()
        if not api_key:
            return None
        base_url = get_nanobanana2_api_base_url().rstrip("/")
        model = get_nanobanana2_model()
        endpoint = f"{base_url}/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": aspect},
            },
        }
        try:
            resp = requests.post(
                endpoint,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=300,
            )
            resp.raise_for_status()
            body = resp.json()
            for candidate in body.get("candidates", []):
                for part in candidate.get("content", {}).get("parts", []):
                    inline = part.get("inlineData") or part.get("inline_data")
                    if not inline:
                        continue
                    data = inline.get("data")
                    mime = inline.get("mimeType") or inline.get("mime_type", "")
                    if data and str(mime).startswith("image/"):
                        img_bytes = base64.b64decode(data)
                        img = Image.open(BytesIO(img_bytes)).convert("RGB")
                        img = img.resize((1920, 1080), Image.LANCZOS)
                        path = os.path.join(ROOT_DIR, ".mp", f"lf-img-{uuid4().hex[:8]}.jpg")
                        img.save(path, "JPEG", quality=90)
                        return path
        except Exception as e:
            if get_verbose():
                warning(f"Gemini image failed: {e}")
        return None

    def generate_images(self) -> List[str]:
        prompts = self.generate_image_prompts()
        self.images = []
        for i, prompt in enumerate(prompts):
            if get_verbose():
                info(f"Generating image {i+1}/{len(prompts)}...")
            path = self._generate_image_gemini(prompt, aspect="16:9")
            if path:
                self.images.append(path)
            else:
                # Fallback: picsum landscape placeholder
                try:
                    import hashlib
                    seed = hashlib.md5(prompt.encode()).hexdigest()[:8]
                    r = requests.get(f"https://picsum.photos/seed/{seed}/1920/1080", timeout=30)
                    r.raise_for_status()
                    img = Image.open(BytesIO(r.content)).convert("RGB")
                    path = os.path.join(ROOT_DIR, ".mp", f"lf-img-fallback-{i}.jpg")
                    img.save(path, "JPEG", quality=85)
                    self.images.append(path)
                except Exception:
                    pass
        return self.images

    # ------------------------------------------------------------------
    # Step 6: Thumbnail
    # ------------------------------------------------------------------

    def generate_thumbnail(self) -> str:
        thumb_text = generate_text(
            f"Write a 4-6 word ALL CAPS YouTube thumbnail title for: {self.subject}.\n"
            f"Make it shocking, controversial, or deeply curious.\n"
            f"Examples: 'THE TRUTH THEY HIDE FROM YOU', 'WHAT THEY DON'T TELL YOU'\n"
            f"Return ONLY the title."
        ).strip().upper()
        if len(thumb_text) > 45:
            thumb_text = " ".join(thumb_text.split()[:5])

        # Background image
        thumb_prompt = (
            f"Epic dramatic YouTube thumbnail background for a video about {self.subject}. "
            f"Dark mysterious atmosphere, cinematic quality, no text, high contrast, "
            f"emotionally powerful, professional photography."
        )
        bg_path = self._generate_image_gemini(thumb_prompt, aspect="16:9")
        if not bg_path and self.images:
            bg_path = self.images[0]

        if not bg_path:
            if get_verbose():
                warning("No thumbnail background available — skipping thumbnail.")
            return ""

        self.thumbnail_path = self._add_thumbnail_text(bg_path, thumb_text)
        return self.thumbnail_path

    def _add_thumbnail_text(self, bg_path: str, text: str) -> str:
        img = Image.open(bg_path).convert("RGBA")
        W, H = img.size

        # Dark gradient on bottom 40%
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        grad_start = int(H * 0.60)
        for y in range(grad_start, H):
            alpha = int(220 * (y - grad_start) / (H - grad_start))
            ov_draw.rectangle([(0, y), (W, y + 1)], fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img, overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # Font
        font_path = os.path.join(get_fonts_dir(), get_font())
        try:
            font = ImageFont.truetype(font_path, 95)
        except Exception:
            font = ImageFont.load_default()

        # Word wrap to 85% of width
        words = text.split()
        lines, current = [], ""
        for word in words:
            test = (current + " " + word).strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] > W * 0.85 and current:
                lines.append(current)
                current = word
            else:
                current = test
        if current:
            lines.append(current)

        line_h = 108
        y = H - (len(lines) * line_h) - 55
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            x = (W - (bbox[2] - bbox[0])) // 2
            # Black shadow
            for dx, dy in [(4, 4), (-4, 4), (4, -4), (-4, -4)]:
                draw.text((x + dx, y + dy), line, font=font, fill=(0, 0, 0))
            # Bright yellow text
            draw.text((x, y), line, font=font, fill=(255, 220, 0))
            y += line_h

        out_path = os.path.join(ROOT_DIR, ".mp", f"thumbnail-{uuid4().hex[:6]}.jpg")
        img.save(out_path, "JPEG", quality=95)
        if get_verbose():
            info(f"Thumbnail saved: {out_path}")
        return out_path

    # ------------------------------------------------------------------
    # Step 7: TTS
    # ------------------------------------------------------------------

    def generate_tts(self) -> str:
        from classes.Tts import TTS
        tts = TTS()
        path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".wav")
        clean_script = re.sub(r"[^\w\s.?!,]", "", self.script)
        tts.synthesize(clean_script, path)
        self.tts_path = path
        if get_verbose():
            info(f"TTS written to: {path}")
        return path

    # ------------------------------------------------------------------
    # Step 8: Subtitles
    # ------------------------------------------------------------------

    @staticmethod
    def _fmt_ts(seconds: float) -> str:
        ms = max(0, int(round(seconds * 1000)))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    def generate_subtitles(self) -> str:
        srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")
        provider = get_stt_provider()

        if provider == "third_party_assemblyai":
            import assemblyai as aai
            aai.settings.api_key = get_assemblyai_api_key()
            transcript = aai.Transcriber().transcribe(self.tts_path)
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(transcript.export_subtitles_srt())
        else:
            from faster_whisper import WhisperModel
            model = WhisperModel(
                get_whisper_model(),
                device=get_whisper_device(),
                compute_type=get_whisper_compute_type(),
            )
            segments, _ = model.transcribe(self.tts_path, vad_filter=True)
            lines = []
            for idx, seg in enumerate(segments, 1):
                text = str(seg.text).strip()
                if not text:
                    continue
                lines += [str(idx), f"{self._fmt_ts(seg.start)} --> {self._fmt_ts(seg.end)}", text, ""]
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))

        equalize_subtitles(srt_path, 10)
        return srt_path

    # ------------------------------------------------------------------
    # Step 9: Combine (1920x1080 MoviePy)
    # ------------------------------------------------------------------

    def combine(self) -> str:
        from moviepy.editor import (
            AudioFileClip, ImageClip, CompositeVideoClip,
            CompositeAudioClip, concatenate_videoclips,
        )
        import random

        if not self.images:
            error("No images — cannot combine video.")
            return ""

        tts_clip = AudioFileClip(self.tts_path)
        max_duration = tts_clip.duration
        req_dur = max_duration / len(self.images)

        clips = []
        tot_dur = 0.0
        while tot_dur < max_duration:
            for img_path in self.images:
                if tot_dur >= max_duration:
                    break
                clip = ImageClip(img_path).set_duration(req_dur).set_fps(30)
                iw, ih = clip.size
                target_ratio = 1920 / 1080
                if iw / ih > target_ratio:
                    new_w = int(ih * target_ratio)
                    clip = clip.crop(x1=(iw - new_w) // 2, x2=(iw + new_w) // 2)
                else:
                    new_h = int(iw / target_ratio)
                    clip = clip.crop(y1=(ih - new_h) // 2, y2=(ih + new_h) // 2)
                clip = clip.resize((1920, 1080))
                clips.append(clip)
                tot_dur += req_dur

        final = concatenate_videoclips(clips).set_duration(max_duration)

        # Background music
        try:
            songs_dir = os.path.join(ROOT_DIR, "songs")
            songs = [f for f in os.listdir(songs_dir) if f.endswith(".mp3")]
            if songs:
                song = AudioFileClip(os.path.join(songs_dir, random.choice(songs)))
                import moviepy.audio.fx.all as afx_all
                if song.duration < max_duration:
                    song = afx_all.audio_loop(song, duration=max_duration)
                else:
                    song = song.set_duration(max_duration)
                song = song.volumex(0.07)
                audio = CompositeAudioClip([tts_clip, song])
            else:
                audio = tts_clip
        except Exception:
            audio = tts_clip

        final = final.set_audio(audio)

        # Render video WITHOUT subtitles first (MoviePy SubtitlesClip is too slow for long-form)
        vid_path = os.path.join(ROOT_DIR, ".mp", f"lf-video-{uuid4().hex[:8]}.mp4")
        final.write_videofile(vid_path, threads=get_threads(), fps=24, codec="libx264", preset="faster")

        # Burn subtitles with ffmpeg (much faster than MoviePy compositor)
        try:
            import subprocess as _sp
            srt_path = self.generate_subtitles()
            vid_subs = vid_path.replace(".mp4", "_subs.mp4")
            _sp.run(
                [
                    "ffmpeg", "-y", "-i", vid_path,
                    "-vf", (
                        f"subtitles={srt_path}:force_style="
                        "'FontName=Arial,FontSize=18,PrimaryColour=&H00FFFF00,"
                        "OutlineColour=&H00000000,Outline=3,Alignment=2'"
                    ),
                    "-c:a", "copy", vid_subs,
                ],
                check=True,
                timeout=600,
            )
            os.replace(vid_subs, vid_path)
        except Exception as e:
            if get_verbose():
                warning(f"Subtitles skipped: {e}")

        self.video_path = vid_path
        if get_verbose():
            success(f"Long-form video saved: {vid_path}")
        return vid_path

    # ------------------------------------------------------------------
    # Step 10: Upload to YouTube
    # ------------------------------------------------------------------

    @staticmethod
    def _get_yt_credentials():
        import json
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

        token_json = os.environ.get("YOUTUBE_TOKEN_JSON")
        if token_json:
            creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
        else:
            token_path = os.path.join(ROOT_DIR, "token.json")
            if not os.path.exists(token_path):
                raise FileNotFoundError(
                    "token.json not found. Run: python scripts/setup_youtube_auth.py"
                )
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        return creds

    def upload_video(self) -> str:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        try:
            creds = self._get_yt_credentials()
            youtube = build("youtube", "v3", credentials=creds)

            body = {
                "snippet": {
                    "title": self.metadata.get("title", self.subject)[:100],
                    "description": self.metadata.get("description", "")[:5000],
                    "tags": self.metadata.get("tags", []),
                    "categoryId": "22",
                },
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": get_is_for_kids(),
                },
            }

            media = MediaFileUpload(self.video_path, chunksize=-1, resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

            if get_verbose():
                info("Uploading video to YouTube...")
            response = None
            while response is None:
                _, response = request.next_chunk()

            video_id = response["id"]
            video_url = f"https://youtube.com/watch?v={video_id}"
            if get_verbose():
                success(f"Long-form uploaded: {video_url}")

            if self.thumbnail_path and os.path.exists(self.thumbnail_path):
                try:
                    youtube.thumbnails().set(
                        videoId=video_id,
                        media_body=MediaFileUpload(self.thumbnail_path),
                    ).execute()
                    if get_verbose():
                        info("Thumbnail uploaded.")
                except Exception as _te:
                    if get_verbose():
                        warning(f"Thumbnail upload skipped: {_te}")

            return video_url

        except Exception as e:
            import traceback
            warning(f"Long-form upload error: {e}")
            traceback.print_exc()
            return ""

    # ------------------------------------------------------------------
    # Run pipeline
    # ------------------------------------------------------------------

    def run(self) -> dict:
        info("Generating topic...")
        self.generate_topic()
        info(f"Topic: {self.subject}")

        info("Generating script (section by section)...")
        self.generate_script()
        info(f"Script: {len(self.script.split())} words")

        info("Generating metadata...")
        self.generate_metadata()

        info("Generating images (16:9)...")
        self.generate_images()

        info("Generating thumbnail...")
        self.generate_thumbnail()

        info("Generating TTS audio...")
        self.generate_tts()

        info("Combining 1920x1080 video...")
        self.combine()

        info("Uploading to YouTube...")
        url = self.upload_video()

        return {
            "id": str(uuid4()),
            "subject": self.subject,
            "title": self.metadata.get("title", ""),
            "url": url,
            "video_path": self.video_path,
            "thumbnail_path": self.thumbnail_path,
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
