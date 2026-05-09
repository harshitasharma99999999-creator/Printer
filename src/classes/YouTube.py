import re
import base64
import json
import time
import os
import requests

from utils import *
from cache import *
from .Tts import TTS
from llm_provider import generate_text
from config import *
from status import *
from uuid import uuid4
from constants import *
from typing import List
from moviepy.editor import *
from moviepy.config import change_settings
from moviepy.video.fx.crop import crop as mpy_crop
from termcolor import colored
from moviepy.video.tools.subtitles import SubtitlesClip
from datetime import datetime


class YouTube:
    """
    Class for YouTube Automation.

    Steps to create a YouTube Short:
    1. Generate a topic [DONE]
    2. Generate a script [DONE]
    3. Generate metadata (Title, Description, Tags) [DONE]
    4. Generate AI Image Prompts [DONE]
    4. Generate Images based on generated Prompts [DONE]
    5. Convert Text-to-Speech [DONE]
    6. Show images each for n seconds, n: Duration of TTS / Amount of images [DONE]
    7. Combine Concatenated Images with the Text-to-Speech [DONE]
    """

    def __init__(
        self,
        account_uuid: str,
        account_nickname: str,
        fp_profile_path: str,
        niche: str,
        language: str,
    ) -> None:
        """
        Constructor for YouTube Class.

        Args:
            account_uuid (str): The unique identifier for the YouTube account.
            account_nickname (str): The nickname for the YouTube account.
            fp_profile_path (str): Path to the firefox profile that is logged into the specificed YouTube Account.
            niche (str): The niche of the provided YouTube Channel.
            language (str): The language of the Automation.

        Returns:
            None
        """
        self._account_uuid: str = account_uuid
        self._account_nickname: str = account_nickname
        self._fp_profile_path: str = fp_profile_path
        self._niche: str = niche
        self._language: str = language

        self.images = []
        os.environ["IMAGEMAGICK_BINARY"] = get_imagemagick_path()
        change_settings({"IMAGEMAGICK_BINARY": get_imagemagick_path()})

    def set_subject(self, subject: str) -> None:
        """Override topic generation with a specific subject (e.g. product name)."""
        self.subject = subject

    @property
    def niche(self) -> str:
        """
        Getter Method for the niche.

        Returns:
            niche (str): The niche
        """
        return self._niche

    @property
    def language(self) -> str:
        """
        Getter Method for the language to use.

        Returns:
            language (str): The language
        """
        return self._language

    def generate_response(self, prompt: str, model_name: str = None) -> str:
        """
        Generates an LLM Response based on a prompt and the user-provided model.

        Args:
            prompt (str): The prompt to use in the text generation.

        Returns:
            response (str): The generated AI Repsonse.
        """
        return generate_text(prompt, model_name=model_name)

    def generate_topic(self) -> str:
        """
        Generates a topic based on the YouTube Channel niche.

        Returns:
            topic (str): The generated topic.
        """
        completion = self.generate_response(
            f"""Generate a compelling YouTube Shorts topic about: {self.niche}
Style: like the channel "YourInnerGuide" — deep, guiding, truth-revealing. The video must feel like a personal spiritual guide is speaking directly to the viewer, revealing an ultimate truth that changes how they see reality.
Use formats like:
- "You Are Not Who You Think You Are — The Truth About Your Consciousness"
- "The Reality You See Is Not Real — Here Is What Actually Is"
- "You Came Here To Shift Reality — This Is How You Do It"
- "The Universe Has Been Trying To Tell You This Your Entire Life"
- "You Are Already Living In Multiple Realities — Here Is The Proof"
- "This Is The ONLY Truth You Need To Shift Your Reality Forever"
- "Stop Trying To Manifest — Do This Instead And Watch Everything Change"
Return ONLY the video topic as one sentence. Nothing else."""
        )

        if not completion:
            error("Failed to generate Topic.")

        self.subject = completion

        return completion

    def generate_script(self) -> str:
        """
        Generate a script for a video, depending on the subject of the video, the number of paragraphs, and the AI model.

        Returns:
            script (str): The script of the video.
        """
        sentence_length = get_script_sentence_length()
        prompt = f"""You are a deeply wise spiritual guide — calm, certain, and profound. Your words carry the weight of ultimate truth. You are like "YourInnerGuide" on YouTube.
Write a script of exactly {sentence_length} sentences about the subject below.

Tone:
- DEEPLY GUIDING — like a wise teacher who knows the truth of consciousness and reality
- Calm yet powerful — every sentence lands like a revelation the viewer has been waiting to hear
- Speak directly to "you" as if you are their inner voice finally speaking out loud
- FIRST SENTENCE must reveal an ultimate truth that immediately makes the viewer stop everything
- Each sentence deepens the truth — like descending deeper into the real nature of existence
- End with a guiding declaration that empowers them to shift their reality right now

Rules:
- Exactly {sentence_length} sentences
- NO markdown, NO titles, NO bullet points
- NO "welcome to" or "in this video" — START with the ultimate truth
- Spoken words only — wise, certain, spiritual, timeless
- Mix short truth bombs with longer profound guiding sentences
- Use YOU and YOUR constantly — speak as their inner guide, their higher self
- Reveal truths about: consciousness, reality, who they truly are, why they are here, how reality works
- Language: {self.language}

Subject: {self.subject}"""
        completion = self.generate_response(prompt)

        # Apply regex to remove *
        completion = re.sub(r"\*", "", completion)

        if not completion:
            error("The generated script is empty.")
            return

        if len(completion) > 5000:
            if get_verbose():
                warning("Generated Script is too long. Retrying...")
            return self.generate_script()

        self.script = completion

        return completion

    def _get_product_affiliate_link(self) -> str:
        """
        Finds an exact Amazon product matching the video topic and returns a direct
        affiliate link (/dp/ASIN?tag=...). Falls back to a topic-relevant search URL.
        """
        import requests as _req
        import re as _re
        from urllib.parse import urlparse as _urlparse, parse_qs as _parse_qs, quote_plus as _qp

        base = get_affiliate_link()
        # Extract affiliate tag from the configured URL
        tag = _parse_qs(_urlparse(base).query).get("tag", ["harshita000-21"])[0]

        # LLM extracts 2-3 product keywords from the video subject
        kw_prompt = (
            f"Extract 2-3 Amazon product search keywords from this YouTube video topic. "
            f"Think: what physical or digital product would someone watching this video want to buy? "
            f"Return ONLY a short search phrase (e.g. 'meditation cushion', 'journal notebook'), nothing else.\n"
            f"Topic: {self.subject}"
        )
        try:
            keywords = generate_text(kw_prompt).strip().strip('"').strip("'")
        except Exception:
            keywords = ""

        if not keywords:
            return base  # fallback to static config link

        encoded = _qp(keywords)
        search_url = f"https://www.amazon.in/s?k={encoded}&tag={tag}"

        # Scrape first product ASIN from Amazon search results
        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "en-IN,en;q=0.9",
            }
            r = _req.get(search_url, headers=headers, timeout=12)
            asins = _re.findall(r"/dp/([A-Z0-9]{10})", r.text)
            if asins:
                asin = asins[0]
                product_url = f"https://www.amazon.in/dp/{asin}?tag={tag}"
                if get_verbose():
                    info(f"Affiliate product link: {product_url} (keywords: {keywords})")
                return product_url
        except Exception as e:
            if get_verbose():
                warning(f"Amazon ASIN scrape failed ({e}), using search URL.")

        # Still topic-relevant — far better than a generic category page
        if get_verbose():
            info(f"Affiliate search link: {search_url}")
        return search_url

    def generate_metadata(self) -> dict:
        """
        Generates Video metadata for the to-be-uploaded YouTube Short (Title, Description, Tags).

        Returns:
            metadata (dict): The generated metadata.
        """
        title = self.generate_response(
            f"""Generate a YouTube video title for the following subject.
Style: Jung Thoughts channel — use formats like:
"What X Really Becomes", "X's Uncomfortable Truth", "The Hidden Truth About X", "Why X – A Warning"
Include 2-3 hashtags like #Psychology #JungThoughts #Spirituality
Only return the title. Under 100 characters.
Subject: {self.subject}"""
        )

        if len(title) > 100:
            if get_verbose():
                warning("Generated Title is too long. Retrying...")
            return self.generate_metadata()

        description = self.generate_response(
            f"Please generate a YouTube Video Description for the following script: {self.script}. "
            f"Tone: calm, confident, helpful. No hype. No markdown. "
            f"Only return the description, nothing else."
        )

        # Generate relevant tags based on the subject
        tags_response = self.generate_response(
            f"Generate 10-15 relevant YouTube tags for a video about: {self.subject}. "
            f"Return ONLY a comma-separated list of tags, nothing else. "
            f"Tags should be short (1-3 words), relevant to the topic, and optimized for search."
        )
        
        # Parse tags from response
        tags = [tag.strip() for tag in tags_response.split(',') if tag.strip()]
        broad_tags = [
            "manifestation",
            "law of attraction",
            "spiritual awakening",
            "mindset",
            "motivation",
            "self improvement",
            "consciousness",
            "healing",
            "energy",
            "shorts",
        ]
        for tag in broad_tags:
            if tag.lower() not in {t.lower() for t in tags}:
                tags.append(tag)
        tags = tags[:15]  # YouTube allows max 15 tags
        
        affiliate_link = self._get_product_affiliate_link()
        if affiliate_link:
            description += f"\n\n🛒 Recommended → {affiliate_link}"
            # Write for Instagram runner to pick up in the same CI run
            try:
                with open(os.path.join(ROOT_DIR, ".mp", "affiliate_link.txt"), "w") as _f:
                    _f.write(affiliate_link)
            except Exception:
                pass

        # Add non-salesy CTA for the matching eBook (if available)
        try:
            from marketing import build_youtube_description, get_latest_ebook_url

            mp_dir = os.path.join(ROOT_DIR, ".mp")
            ebook_url = get_latest_ebook_url(mp_dir)
            description = build_youtube_description(
                base_description=description,
                topic=self.subject,
                ebook_url=ebook_url,
                affiliate_link=affiliate_link,
                include_disclosure=True,
                is_shorts=True,
            )
        except Exception:
            pass

        # #Shorts tag is required for YouTube to classify vertical videos as Shorts
        broad_hashtags = "#Shorts #Manifestation #LawOfAttraction #Motivation #Mindset"
        if "#Shorts" not in description and "#shorts" not in description:
            description += f"\n\n{broad_hashtags}"
        elif "#Manifestation" not in description and "#manifestation" not in description:
            description += "\n#Manifestation #LawOfAttraction #Motivation #Mindset"

        self.metadata = {"title": title, "description": description, "tags": tags}

        return self.metadata

    def generate_prompts(self, _retries: int = 0) -> List[str]:
        """
        Generates AI Image Prompts based on the provided Video Script.

        Returns:
            image_prompts (List[str]): Generated List of image prompts.
        """
        n_prompts = 5

        prompt = f"""Generate exactly {n_prompts} deeply spiritual and cinematic image prompts for a YouTube Short about consciousness, reality shifting, and inner truth.
Each image must feel like a visual gateway into a higher dimension — breathtaking, otherworldly, and deeply meaningful.
Style: hyper-realistic spiritual photography — soft divine light, cosmic infinity, the feeling of awakening, sacred and timeless.
Use: a lone meditating human bathed in divine golden light, infinite starfields with a silhouette, cosmic doorways opening, the universe inside a human chest, eyes reflecting galaxies, light pouring from hands, ancient temples dissolving into stars.
DO NOT use dark or scary imagery. Only divine, awe-inspiring, deeply peaceful yet powerful visuals.
Return ONLY a JSON array of {n_prompts} strings, nothing else.

Subject: {self.subject}"""

        completion = (
            str(self.generate_response(prompt))
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        image_prompts = []

        try:
            parsed = json.loads(completion)
            if isinstance(parsed, list):
                image_prompts = [str(p) for p in parsed if p]
            elif isinstance(parsed, dict) and "image_prompts" in parsed:
                image_prompts = parsed["image_prompts"]
        except Exception:
            # Try to extract [...] substring
            r = re.compile(r"\[.*?\]", re.DOTALL)
            match = r.search(completion)
            if match:
                try:
                    image_prompts = json.loads(match.group())
                except Exception:
                    pass

        if not image_prompts:
            if _retries < 3:
                if get_verbose():
                    warning("Failed to parse image prompts. Retrying...")
                return self.generate_prompts(_retries=_retries + 1)
            # Fallback: scroll-stopping cinematic prompts
            if get_verbose():
                warning("Using fallback image prompts.")
            image_prompts = [
                f"lone human silhouette sitting in deep meditation on a mountaintop, vast cosmos above, divine golden light pouring down from infinite stars, {self.subject}, 8k cinematic spiritual",
                f"a human figure dissolving into pure white light, the universe expanding from within their chest, reality shifting, awe-inspiring, {self.subject}, hyper-realistic divine",
                f"ancient cosmic doorway opening in the sky above a still lake, perfect reflection, soft golden light streaming through, invitation to higher reality, {self.subject}, cinematic 8k",
                f"extreme close-up of a human eye reflecting an entire galaxy, stars and nebulas inside the iris, the universe looking back, {self.subject}, ultra-detailed spiritual 8k",
                f"human hands open and glowing, streams of soft golden light flowing upward into the cosmos, infinite giving and receiving, {self.subject}, divine cinematic composition",
            ]

        image_prompts = image_prompts[:n_prompts]
        self.image_prompts = image_prompts

        if get_verbose():
            info(f" => Generated Image Prompts: {image_prompts}")
        success(f"Generated {len(image_prompts)} Image Prompts.")

        return image_prompts

    def _persist_image(self, image_bytes: bytes, provider_label: str) -> str:
        """
        Writes generated image bytes to a PNG file in .mp.

        Args:
            image_bytes (bytes): Image payload
            provider_label (str): Label for logging

        Returns:
            path (str): Absolute image path
        """
        image_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".png")

        with open(image_path, "wb") as image_file:
            image_file.write(image_bytes)

        if get_verbose():
            info(f' => Wrote image from {provider_label} to "{image_path}"')

        self.images.append(image_path)
        return image_path

    def generate_image_nanobanana2(self, prompt: str) -> str:
        """
        Generates an AI Image using Nano Banana 2 API (Gemini image API).

        Args:
            prompt (str): Prompt for image generation

        Returns:
            path (str): The path to the generated image.
        """
        print(f"Generating Image using Nano Banana 2 API: {prompt}")

        api_key = get_nanobanana2_api_key()
        if not api_key:
            error("nanobanana2_api_key is not configured.")
            return None

        base_url = get_nanobanana2_api_base_url().rstrip("/")
        model = get_nanobanana2_model()
        aspect_ratio = get_nanobanana2_aspect_ratio()

        endpoint = f"{base_url}/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {"aspectRatio": aspect_ratio},
            },
        }

        try:
            response = requests.post(
                endpoint,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=300,
            )
            response.raise_for_status()
            body = response.json()

            candidates = body.get("candidates", [])
            for candidate in candidates:
                content = candidate.get("content", {})
                for part in content.get("parts", []):
                    inline_data = part.get("inlineData") or part.get("inline_data")
                    if not inline_data:
                        continue
                    data = inline_data.get("data")
                    mime_type = inline_data.get("mimeType") or inline_data.get("mime_type", "")
                    if data and str(mime_type).startswith("image/"):
                        image_bytes = base64.b64decode(data)
                        return self._persist_image(image_bytes, "Nano Banana 2 API")

            if get_verbose():
                warning(f"Nano Banana 2 did not return an image payload. Response: {body}")
            return None
        except Exception as e:
            if get_verbose():
                warning(f"Failed to generate image with Nano Banana 2 API: {str(e)}")
            return None

    def generate_image_free(self, prompt: str) -> str:
        import hashlib
        print(f"Generating Image using Picsum (free): {prompt}")
        seed = hashlib.md5(prompt.encode()).hexdigest()[:8]
        url = f"https://picsum.photos/seed/{seed}/1080/1920"
        try:
            response = requests.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            return self._persist_image(response.content, "Picsum")
        except Exception as e:
            if get_verbose():
                warning(f"Failed to generate image with Picsum: {str(e)}")
            return None

    def generate_image(self, prompt: str) -> str:
        """
        Generates an AI Image based on the given prompt.
        Tries Nano Banana 2 (Gemini) API first, falls back to Picsum if not configured.

        Args:
            prompt (str): Reference for image generation

        Returns:
            path (str): The path to the generated image.
        """
        # Try AI generation first if API key is configured
        api_key = get_nanobanana2_api_key()
        if api_key:
            result = self.generate_image_nanobanana2(prompt)
            if result:
                return result
            if get_verbose():
                warning("AI image generation failed, falling back to Picsum")
        
        # Fallback to Picsum
        return self.generate_image_free(prompt)

    def generate_script_to_speech(self, tts_instance: TTS) -> str:
        """
        Converts the generated script into Speech using KittenTTS and returns the path to the wav file.

        Args:
            tts_instance (tts): Instance of TTS Class.

        Returns:
            path_to_wav (str): Path to generated audio (WAV Format).
        """
        path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".wav")

        # Clean script, remove every character that is not a word character, a space, a period, a question mark, or an exclamation mark.
        self.script = re.sub(r"[^\w\s.?!]", "", self.script)

        tts_instance.synthesize(self.script, path)

        self.tts_path = path

        if get_verbose():
            info(f' => Wrote TTS to "{path}"')

        return path

    def add_video(self, video: dict) -> None:
        """
        Adds a video to the cache.

        Args:
            video (dict): The video to add

        Returns:
            None
        """
        cache = get_youtube_cache_path()

        if not os.path.exists(cache):
            with open(cache, "w", encoding="utf-8") as file:
                json.dump({"accounts": []}, file, indent=4)

        with open(cache, "r", encoding="utf-8") as file:
            previous_json = json.loads(file.read())

            # Find our account
            accounts = previous_json.get("accounts", [])
            found = False
            for account in accounts:
                if account["id"] == self._account_uuid:
                    account.setdefault("videos", []).append(video)
                    found = True
                    break

            if not found:
                accounts.append(
                    {
                        "id": self._account_uuid,
                        "nickname": self._account_nickname,
                        "firefox_profile": self._fp_profile_path,
                        "niche": self._niche,
                        "language": self._language,
                        "videos": [video],
                    }
                )
                previous_json["accounts"] = accounts

            # Commit changes
            with open(cache, "w", encoding="utf-8") as f:
                json.dump(previous_json, f, indent=4)

    def generate_subtitles(self, audio_path: str) -> str:
        """
        Generates subtitles for the audio using the configured STT provider.

        Args:
            audio_path (str): The path to the audio file.

        Returns:
            path (str): The path to the generated SRT File.
        """
        provider = str(get_stt_provider() or "local_whisper").lower()

        if provider == "local_whisper":
            return self.generate_subtitles_local_whisper(audio_path)

        if provider == "third_party_assemblyai":
            return self.generate_subtitles_assemblyai(audio_path)

        warning(f"Unknown stt_provider '{provider}'. Falling back to local_whisper.")
        return self.generate_subtitles_local_whisper(audio_path)

    def generate_subtitles_assemblyai(self, audio_path: str) -> str:
        """
        Generates subtitles using AssemblyAI.

        Args:
            audio_path (str): Audio file path

        Returns:
            path (str): Path to SRT file
        """
        try:
            import assemblyai as aai
        except ImportError as exc:
            raise RuntimeError(
                "AssemblyAI subtitles require the 'assemblyai' package to be installed."
            ) from exc

        aai.settings.api_key = get_assemblyai_api_key()
        config = aai.TranscriptionConfig()
        transcriber = aai.Transcriber(config=config)
        transcript = transcriber.transcribe(audio_path)
        subtitles = transcript.export_subtitles_srt()

        srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")

        with open(srt_path, "w") as file:
            file.write(subtitles)

        return srt_path

    def _format_srt_timestamp(self, seconds: float) -> str:
        """
        Formats a timestamp in seconds to SRT format.

        Args:
            seconds (float): Seconds

        Returns:
            ts (str): HH:MM:SS,mmm
        """
        total_millis = max(0, int(round(seconds * 1000)))
        hours = total_millis // 3600000
        minutes = (total_millis % 3600000) // 60000
        secs = (total_millis % 60000) // 1000
        millis = total_millis % 1000
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def generate_subtitles_local_whisper(self, audio_path: str) -> str:
        """
        Generates subtitles using local Whisper (faster-whisper).

        Args:
            audio_path (str): Audio file path

        Returns:
            path (str): Path to SRT file
        """
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            error(
                "Local STT selected but 'faster-whisper' is not installed. "
                "Install it or switch stt_provider to third_party_assemblyai."
            )
            raise

        model = WhisperModel(
            get_whisper_model(),
            device=get_whisper_device(),
            compute_type=get_whisper_compute_type(),
        )
        segments, _ = model.transcribe(audio_path, vad_filter=True)

        lines = []
        for idx, segment in enumerate(segments, start=1):
            start = self._format_srt_timestamp(segment.start)
            end = self._format_srt_timestamp(segment.end)
            text = str(segment.text).strip()

            if not text:
                continue

            lines.append(str(idx))
            lines.append(f"{start} --> {end}")
            lines.append(text)
            lines.append("")

        subtitles = "\n".join(lines)
        srt_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".srt")
        with open(srt_path, "w", encoding="utf-8") as file:
            file.write(subtitles)

        return srt_path

    def combine(self) -> str:
        """
        Combines everything into the final video.

        Returns:
            path (str): The path to the generated MP4 File.
        """
        combined_image_path = os.path.join(ROOT_DIR, ".mp", str(uuid4()) + ".mp4")
        threads = get_threads()
        tts_clip = AudioFileClip(self.tts_path)
        max_duration = tts_clip.duration
        req_dur = max_duration / len(self.images)

        # Make a generator that returns a TextClip when called with consecutive
        generator = lambda txt: TextClip(
            txt,
            font=os.path.join(get_fonts_dir(), get_font()),
            fontsize=100,
            color="#FFFF00",
            stroke_color="black",
            stroke_width=5,
            size=(1080, 1920),
            method="caption",
        )

        print(colored("[+] Combining images...", "blue"))

        clips = []
        tot_dur = 0
        # Add downloaded clips over and over until the duration of the audio (max_duration) has been reached
        while tot_dur < max_duration:
            for image_path in self.images:
                clip = ImageClip(image_path)
                clip.duration = req_dur
                clip = clip.set_fps(30)

                # Not all images are same size,
                # so we need to resize them
                if round((clip.w / clip.h), 4) < 0.5625:
                    if get_verbose():
                        info(f" => Resizing Image: {image_path} to 1080x1920")
                    clip = mpy_crop(
                        clip,
                        width=clip.w,
                        height=round(clip.w / 0.5625),
                        x_center=clip.w / 2,
                        y_center=clip.h / 2,
                    )
                else:
                    if get_verbose():
                        info(f" => Resizing Image: {image_path} to 1920x1080")
                    clip = mpy_crop(
                        clip,
                        width=round(0.5625 * clip.h),
                        height=clip.h,
                        x_center=clip.w / 2,
                        y_center=clip.h / 2,
                    )
                clip = clip.resize((1080, 1920))

                # FX (Fade In)
                # clip = clip.fadein(2)

                clips.append(clip)
                tot_dur += clip.duration

        final_clip = concatenate_videoclips(clips)
        final_clip = final_clip.set_fps(30)
        random_song = choose_random_song()

        subtitles = None
        try:
            subtitles_path = self.generate_subtitles(self.tts_path)
            equalize_subtitles(subtitles_path, 10)
            subtitles = SubtitlesClip(subtitles_path, generator)
            subtitles.set_pos(("center", "center"))
        except Exception as e:
            warning(f"Failed to generate subtitles, continuing without subtitles: {e}")

        if random_song:
            random_song_clip = AudioFileClip(random_song).set_fps(44100)
            random_song_clip = random_song_clip.fx(afx.volumex, 0.1)
            comp_audio = CompositeAudioClip([tts_clip.set_fps(44100), random_song_clip])
        else:
            comp_audio = tts_clip.set_fps(44100)

        final_clip = final_clip.set_audio(comp_audio)
        final_clip = final_clip.set_duration(tts_clip.duration)

        if subtitles is not None:
            final_clip = CompositeVideoClip([final_clip, subtitles])

        final_clip.write_videofile(combined_image_path, threads=threads)

        success(f'Wrote Video to "{combined_image_path}"')

        # Stable path for downstream automations (Instagram, artifacts, etc.)
        try:
            stable_path = os.path.join(ROOT_DIR, ".mp", "last_short.mp4")
            try:
                if os.path.exists(stable_path):
                    os.remove(stable_path)
            except Exception:
                pass
            # Copy rather than rename so the random UUID file remains for debugging.
            import shutil

            shutil.copyfile(combined_image_path, stable_path)
            with open(os.path.join(ROOT_DIR, ".mp", "last_short_path.txt"), "w", encoding="utf-8") as f:
                f.write(os.path.abspath(stable_path))
            if get_verbose():
                info(f"Saved stable short path: {stable_path}")
        except Exception as _se:
            if get_verbose():
                warning(f"Failed to write stable short marker file: {_se}")

        return combined_image_path

    def generate_video(self, tts_instance: TTS) -> str:
        """
        Generates a YouTube Short based on the provided niche and language.

        Args:
            tts_instance (TTS): Instance of TTS Class.

        Returns:
            path (str): The path to the generated MP4 File.
        """
        try:
            # Generate the Topic (skip if subject already set via set_subject())
            if not hasattr(self, 'subject') or not self.subject:
                self.generate_topic()

            # Fail fast if YouTube token is invalid/missing upload scope, so we don't waste time rendering.
            try:
                from utils import preflight_youtube_api

                creds = self._get_yt_credentials()
                preflight_youtube_api(creds, verbose=get_verbose())
            except Exception as e:
                # Keep error concise for GitHub Actions logs.
                raise RuntimeError(str(e)) from e

            # Generate the Script
            self.generate_script()

            # Optional: auto-generate + publish a companion eBook (Gumroad) for this video.
            # This runs BEFORE metadata so the Gumroad link can be injected into the description.
            auto_ebook = str(os.environ.get("YOUTUBE_AUTO_EBOOK", "")).strip().lower() in ("1", "true", "yes")
            if auto_ebook:
                require_ebook = str(os.environ.get("YOUTUBE_REQUIRE_EBOOK", "true")).strip().lower() in ("1", "true", "yes")
                from config import get_gumroad_access_token
                from classes.EBook import EBook

                gumroad_ok = bool(
                    (os.environ.get("GUMROAD_ACCESS_TOKEN", "").strip())
                    or (os.environ.get("GUMROAD_SESSION_JSON", "").strip())
                    or (
                        os.environ.get("GUMROAD_EMAIL", "").strip()
                        and os.environ.get("GUMROAD_PASSWORD", "").strip()
                    )
                    or (get_gumroad_access_token() or "").strip()
                )
                if not gumroad_ok:
                    msg = (
                        "YOUTUBE_AUTO_EBOOK is enabled but no Gumroad credentials were found. "
                        "Set `GUMROAD_ACCESS_TOKEN` (recommended) or `GUMROAD_SESSION_JSON` "
                        "or `GUMROAD_EMAIL`+`GUMROAD_PASSWORD`."
                    )
                    if require_ebook:
                        raise RuntimeError(msg)
                    warning(msg)
                    auto_ebook = False

            if auto_ebook:
                keys = ["EBOOK_TOPIC", "EBOOK_CONTEXT", "EBOOK_SKIP_KDP", "EBOOK_SKIP_PRINT"]
                prev = {k: os.environ.get(k) for k in keys}
                try:
                    os.environ["EBOOK_TOPIC"] = self.subject
                    os.environ["EBOOK_CONTEXT"] = (self.script or "")[:5000]
                    os.environ.setdefault("EBOOK_SKIP_KDP", "1")
                    os.environ.setdefault("EBOOK_SKIP_PRINT", "1")

                    eb = EBook()
                    result = eb.run()
                    if not result.get("gumroad_url"):
                        msg = "Companion eBook publish failed (no Gumroad URL). Check `.mp/gumroad_*` debug files and your Gumroad token/settings."
                        if require_ebook:
                            raise RuntimeError(msg)
                        warning(msg)
                finally:
                    for k, v in prev.items():
                        if v is None:
                            os.environ.pop(k, None)
                        else:
                            os.environ[k] = v

            # Generate the Metadata
            self.generate_metadata()

            # Generate the Image Prompts
            self.generate_prompts()

            # Generate the Images
            for prompt in self.image_prompts:
                self.generate_image(prompt)

            # Generate the TTS
            self.generate_script_to_speech(tts_instance)

            # Combine everything
            path = self.combine()

            if get_verbose():
                info(f" => Generated Video: {path}")

            self.video_path = os.path.abspath(path)

            return path
            
        except Exception as e:
            error(f"Video generation failed: {e}")
            if get_verbose():
                import traceback
                traceback.print_exc()
            raise

    @staticmethod
    def _get_yt_credentials():
        import json
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        required_scopes = ["https://www.googleapis.com/auth/youtube.upload"]
        token_json = os.environ.get("YOUTUBE_TOKEN_JSON", "").strip()

        token_info = None
        if token_json:
            token_info = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(token_info)
        else:
            token_path = os.path.join(ROOT_DIR, "token.json")
            if not os.path.exists(token_path):
                raise FileNotFoundError(
                    "token.json not found. Run scripts/setup_youtube_auth.py first."
                )
            with open(token_path, "r", encoding="utf-8") as f:
                token_info = json.loads(f.read())
            creds = Credentials.from_authorized_user_file(token_path)

        if not getattr(creds, "scopes", None) and isinstance(token_info, dict):
            raw_scopes = token_info.get("scopes") or token_info.get("scope")
            if isinstance(raw_scopes, str):
                creds.scopes = [s for s in raw_scopes.split() if s]
            elif isinstance(raw_scopes, list):
                creds.scopes = [str(s) for s in raw_scopes if str(s).strip()]

        # Ensure scopes are set
        if not getattr(creds, "scopes", None):
            creds.scopes = required_scopes

        if creds.expired and creds.refresh_token:
            try:
                if get_verbose():
                    info("Refreshing YouTube OAuth token...")
                creds.refresh(Request())
            except Exception as refresh_error:
                if get_verbose():
                    warning(f"Token refresh failed: {refresh_error}")

        return creds

    def upload_video(self) -> bool:
        """
        Uploads the video to YouTube via Data API v3.

        Returns:
            success (bool): Whether the upload was successful or not.
        """
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
        from utils import format_youtube_http_error

        try:
            if not getattr(self, "video_path", None):
                raise RuntimeError("No rendered video found. Run generate_video() before upload.")
            if not os.path.exists(self.video_path):
                raise FileNotFoundError(f"Rendered video not found: {self.video_path}")
            if not getattr(self, "metadata", None):
                if not getattr(self, "subject", None):
                    raise RuntimeError("Video subject is missing, so metadata cannot be generated.")
                if not getattr(self, "script", None):
                    self.script = getattr(self, "subject", "")
                self.generate_metadata()

            creds = self._get_yt_credentials()
            youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
            verbose = get_verbose()

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

            if verbose:
                info("Uploading Short to YouTube...")
            response = run_youtube_resumable_upload(
                request,
                verbose=verbose,
                label="Short",
            )

            video_id = response["id"]
            url = build_url(video_id)
            self.uploaded_video_url = url

            if verbose:
                success(f"Short uploaded: {url}")

            self.add_video(
                {
                    "subject": self.subject,
                    "title": self.metadata["title"],
                    "description": self.metadata["description"],
                    "url": url,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
            return True

        except HttpError as e:
            warning(format_youtube_http_error(e))
            if get_verbose():
                import traceback
                traceback.print_exc()
            return False
        except Exception as e:
            import traceback
            warning(f"Short upload error: {e}")
            traceback.print_exc()
            return False

    def get_videos(self) -> List[dict]:
        """
        Gets the uploaded videos from the YouTube Channel.

        Returns:
            videos (List[dict]): The uploaded videos.
        """
        cache_path = get_youtube_cache_path()
        if not os.path.exists(cache_path):
            # Create the cache file
            with open(cache_path, "w", encoding="utf-8") as file:
                json.dump({"accounts": []}, file, indent=4)
            return []

        videos = []
        # Read the cache file
        with open(cache_path, "r", encoding="utf-8") as file:
            previous_json = json.loads(file.read())
            # Find our account
            accounts = previous_json.get("accounts", [])
            for account in accounts:
                if account["id"] == self._account_uuid:
                    videos = account.get("videos", [])

        return videos
