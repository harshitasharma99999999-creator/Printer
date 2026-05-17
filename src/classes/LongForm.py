import os
import re
import time
import json
import uuid
import base64
import requests
import textwrap

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
    "luxury lifestyle and billionaire aesthetics",
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

    def _is_psychology_channel(self) -> bool:
        niche = (self.niche or "").lower()
        return "psychology" in niche or "behavior" in niche or "dark truth" in niche

    def _is_luxury_channel(self) -> bool:
        niche = (self.niche or "").lower()
        nickname = (self.account_nickname or "").lower()
        account_uuid = (self.account_uuid or "").lower()
        luxury_terms = [
            "luxury",
            "rich lifestyle",
            "richlifesytles",
            "wealth",
            "billionaire",
            "supercar",
            "private jet",
            "mansion",
            "old money",
            "yacht",
            "elite",
        ]
        return (
            "billionaireparadise" in nickname
            or "billionaireparadise" in account_uuid
            or any(term in niche for term in luxury_terms)
        )

    # ------------------------------------------------------------------
    # Step 1: Topic
    # ------------------------------------------------------------------

    def generate_topic(self) -> str:
        if self._is_luxury_channel():
            prompt = (
                f"Generate ONE compelling YouTube long-form video topic about {self.niche}.\n"
                f"Style: ultra-luxury, billionaire lifestyle, old money aesthetics, elite routines, private jets, mansions, yachts, supercars, wealth mindset, premium travel, and expensive habits.\n"
                f"The topic must feel aspirational, visually rich, and highly clickable for a luxury lifestyle audience.\n"
                f"Examples:\n"
                f"'Inside The Daily Routine Of Ultra Rich People'\n"
                f"'Luxury Habits That Quietly Signal Real Wealth'\n"
                f"'What Billionaire Travel Really Looks Like'\n"
                f"'The Mansion Details Rich People Always Notice'\n"
                f"'Old Money Rules That Make Luxury Look Effortless'\n"
                f"Return ONLY the topic, nothing else."
            )
            raw = generate_text(prompt).strip()
            self.subject = next(
                (l.strip().strip('"').strip("'") for l in raw.splitlines() if l.strip()),
                raw.split(".")[0].strip()
            )
            return self.subject
        if self._is_psychology_channel():
            prompt = (
                f"Generate ONE compelling long-form YouTube video topic (10-15 minutes) about {self.niche}.\n"
                f"Style: real human psychology, dark truths, hidden motives, emotional patterns, attachment, insecurity, manipulation, power, attraction, and self-deception.\n"
                f"The topic must feel intense, insightful, and highly clickable without sounding fake.\n"
                f"Examples:\n"
                f"'The Dark Truth About Why People Change When They Gain Power'\n"
                f"'What Emotional Unavailability Really Reveals About A Person'\n"
                f"'Why People Only Respect Boundaries They Fear'\n"
                f"'The Brutal Psychology Of Validation, Silence, And Control'\n"
                f"'How Insecurity Secretly Shapes Relationships And Status'\n"
                f"Return ONLY the topic, nothing else."
            )
            raw = generate_text(prompt).strip()
            self.subject = next(
                (l.strip().strip('"').strip("'") for l in raw.splitlines() if l.strip()),
                raw.split(".")[0].strip()
            )
            return self.subject
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
        if self._is_luxury_channel():
            hook = generate_text(
                f"Write a 4-sentence opening for a luxury lifestyle YouTube video about: {self.subject}.\n"
                f"Tone: premium, aspirational, visual, calm, stylish.\n"
                f"Sentence 1 must instantly paint a rich-lifestyle image.\n"
                f"Sentence 2 should reveal a hidden luxury detail most people miss.\n"
                f"Sentence 3 should make the viewer imagine stepping into that world.\n"
                f"Sentence 4 should promise a deeper look into billionaire-level living.\n"
                f"Language: {self.language}. No markdown. Spoken-style lines only."
            ).strip()
            parts.append(hook)

            outline_raw = generate_text(
                f"List exactly 6 section titles for a luxury lifestyle YouTube video about: {self.subject}.\n"
                f"Style: billionaire routines, private jets, supercars, mansions, designer details, luxury travel, old money codes, premium habits.\n"
                f"Format: numbered list 1-6. No explanations."
            ).strip()
            section_titles = []
            for line in outline_raw.splitlines():
                m = re.match(r"^\d+[\.\)]\s*(.+)", line.strip())
                if m:
                    section_titles.append(m.group(1).strip())
            if len(section_titles) < 6:
                section_titles = [
                    "The First Luxury Detail People Notice",
                    "Inside The Billionaire Travel Experience",
                    "Why Mansions Feel Different From Normal Homes",
                    "The Quiet Signals Of Old Money Taste",
                    "How Supercars Shape The Luxury Aesthetic",
                    "What Makes Rich Life Feel So Addictive",
                ]

            for title in section_titles[:6]:
                section = generate_text(
                    f"Write 6 short, highly visual sentences for the section '{title}' in a luxury lifestyle video about: {self.subject}.\n"
                    f"Focus on expensive textures, premium spaces, elite routines, luxury travel, designer details, supercars, mansions, yachts, and aspirational imagery.\n"
                    f"Keep each sentence concise and easy to read on screen. Language: {self.language}. No markdown."
                ).strip()
                parts.append(section)

            cta = generate_text(
                f"Write a 3-sentence closing for a luxury lifestyle YouTube video about: {self.subject}.\n"
                f"Ask viewers to like, comment their dream luxury experience, and subscribe for more billionaire lifestyle content.\n"
                f"Tone: premium, clean, aspirational. Language: {self.language}. Spoken words only."
            ).strip()
            parts.append(cta)

            raw = "\n\n".join(p for p in parts if p)
            self.script = self._clean_script(raw)
            return self.script
        if self._is_psychology_channel():
            hook = generate_text(
                f"Write a 4-sentence opening for a dark human psychology long-form YouTube video about: {self.subject}.\n"
                f"Sentence 1: open with an uncomfortable truth about people that creates immediate curiosity.\n"
                f"Sentence 2: reveal the hidden emotional or behavioral pattern behind it.\n"
                f"Sentence 3: make it personal so the viewer feels they have seen this in their own life.\n"
                f"Sentence 4: promise a deeper understanding of what people rarely say out loud.\n"
                f"Language: {self.language}. No markdown. Spoken words only."
            ).strip()
            parts.append(hook)

            outline_raw = generate_text(
                f"List exactly 5 section titles for a 12-minute YouTube video about: {self.subject}.\n"
                f"Style: human psychology, dark truths, behavior patterns, emotional insight, relationships, power, and self-deception.\n"
                f"Format: numbered list 1-5. No explanations."
            ).strip()
            section_titles = []
            for line in outline_raw.splitlines():
                m = re.match(r"^\d+[\.\)]\s*(.+)", line.strip())
                if m:
                    section_titles.append(m.group(1).strip())
            if len(section_titles) < 5:
                section_titles = [
                    "The Hidden Pattern Most People Miss",
                    "What This Behavior Is Really Protecting",
                    "How Power, Fear, And Validation Shape People",
                    "Why This Pattern Repeats In Relationships",
                    "What To See Clearly From Now On",
                ]

            for title in section_titles[:5]:
                section = generate_text(
                    f"Write 6 insightful spoken sentences for the section '{title}' in a long-form video about: {self.subject}.\n"
                    f"Tone: sharp, calm, observant, psychologically accurate.\n"
                    f"Focus on real motives, insecurity, validation, control, attraction, fear, ego, and self-deception where relevant.\n"
                    f"Language: {self.language}. No markdown. No headers. Spoken words only."
                ).strip()
                parts.append(section)

            cta = generate_text(
                f"Write a 3-sentence closing for a YouTube video about: {self.subject}.\n"
                f"Ask the viewer to like, comment with their observation, and subscribe for more human psychology content.\n"
                f"Tone: direct, reflective, strong. Language: {self.language}. Spoken words only."
            ).strip()
            parts.append(cta)

            raw = "\n\n".join(p for p in parts if p)
            self.script = self._clean_script(raw)
            return self.script

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
        if self._is_luxury_channel():
            title = generate_text(
                f"Write a YouTube video title for: {self.subject}.\n"
                f"Make it SEO-optimized, broad-audience friendly, luxurious, and highly clickable for people interested in rich lifestyle, billionaire lifestyle, luxury travel, supercars, mansions, and old money aesthetics.\n"
                f"Under 70 characters. Return ONLY the title, no quotes."
            ).strip().strip('"').strip("'")
            if len(title) > 100:
                title = title[:97] + "..."

            description = generate_text(
                f"Write a YouTube description for a luxury lifestyle video titled '{title}' about: {self.subject}.\n"
                f"Include SEO keywords naturally: luxury lifestyle, billionaire lifestyle, rich life, old money, private jet, supercars, mansion, wealth habits, luxury travel.\n"
                f"150-200 words. No markdown.\n"
                f"End with: Subscribe for more luxury lifestyle videos."
            ).strip()

            description += "\n\n#LuxuryLifestyle #RichLife #BillionaireLifestyle #OldMoney #LuxuryTravel"
            self.metadata = {
                "title": title,
                "description": description,
                "tags": [
                    "luxury lifestyle",
                    "rich lifestyle",
                    "billionaire lifestyle",
                    "old money",
                    "luxury travel",
                    "private jet",
                    "supercars",
                    "mansion tour",
                    "wealth habits",
                    "elite lifestyle",
                    "luxury video",
                ],
            }
            return self.metadata
        if self._is_psychology_channel():
            title = generate_text(
                f"Write a YouTube video title for: {self.subject}.\n"
                f"Make it SEO-optimized, emotionally sharp, and highly clickable for a human psychology audience. Under 70 characters.\n"
                f"Use dark-truth framing when natural. Return ONLY the title, no quotes."
            ).strip().strip('"').strip("'")
            if len(title) > 100:
                title = title[:97] + "..."

            description = generate_text(
                f"Write a YouTube video description for a video titled '{title}' about: {self.subject}.\n"
                f"Include SEO keywords around psychology, human behavior, dark psychology, relationships, emotional intelligence, and self-awareness naturally.\n"
                f"150-200 words. No markdown.\n"
                f"End with: Subscribe for more human psychology insights."
            ).strip()

            description += "\n\n#HumanPsychology #DarkPsychology #Psychology #HumanBehavior #SelfAwareness"

            affiliate = get_affiliate_link()
            if affiliate:
                description += f"\n\nRecommended:\n{affiliate}"

            try:
                from marketing import build_youtube_description, get_latest_ebook_url

                mp_dir = os.path.join(ROOT_DIR, ".mp")
                ebook_url = get_latest_ebook_url(mp_dir)
                description = build_youtube_description(
                    base_description=description,
                    topic=self.subject,
                    ebook_url=ebook_url,
                    affiliate_link=affiliate,
                    include_disclosure=True,
                    is_shorts=False,
                )
            except Exception:
                pass

            self.metadata = {"title": title, "description": description}
            return self.metadata
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

        # Add a matching eBook CTA (if available)
        try:
            from marketing import build_youtube_description, get_latest_ebook_url

            mp_dir = os.path.join(ROOT_DIR, ".mp")
            ebook_url = get_latest_ebook_url(mp_dir)
            description = build_youtube_description(
                base_description=description,
                topic=self.subject,
                ebook_url=ebook_url,
                affiliate_link=affiliate,
                include_disclosure=True,
                is_shorts=False,
            )
        except Exception:
            pass

        self.metadata = {"title": title, "description": description}
        return self.metadata

    # ------------------------------------------------------------------
    # Step 4: Image prompts (16:9)
    # ------------------------------------------------------------------

    def generate_image_prompts(self) -> List[str]:
        if self._is_luxury_channel():
            raw = generate_text(
                f"Generate 8 CINEMATIC 16:9 image prompts for a luxury lifestyle YouTube video about: {self.subject}.\n"
                f"Style: ultra-premium, glossy black, champagne gold, silver, marble, penthouses, private jets, yachts, supercars, designer interiors, sunset city skylines, wealth aesthetics.\n"
                f"No fantasy, no cartoons, no text in the image.\n"
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
                f"private jet interior with black leather, champagne gold lighting, cinematic luxury aesthetic, {self.subject}",
                f"ultra premium supercar outside a modern mansion at dusk, glossy black and gold palette, {self.subject}",
                f"billionaire penthouse skyline view with marble floors and designer furniture, {self.subject}",
                f"luxury yacht deck at sunset with elite travel energy, polished chrome and gold details, {self.subject}",
                f"old money wardrobe detail with luxury watch, cufflinks, black suit, elegant moody light, {self.subject}",
                f"mansion infinity pool overlooking city lights, premium architecture, {self.subject}",
                f"first class luxury travel lounge with designer textures and wealthy atmosphere, {self.subject}",
                f"high end garage with exotic supercars and dramatic premium lighting, {self.subject}",
            ]
        if self._is_psychology_channel():
            raw = generate_text(
                f"Generate 8 CINEMATIC 16:9 image prompts for a human psychology YouTube video about: {self.subject}.\n"
                f"Style: realistic, emotionally intense, dark but tasteful, dramatic lighting, expressive faces, tense body language, mirrors, isolation, status dynamics, relationship distance, subtle symbolism.\n"
                f"No fantasy, no monsters, no gore. Keep it grounded in real human emotion and behavior.\n"
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
                f"realistic cinematic portrait of hidden emotion and guarded expression, human psychology theme, {self.subject}",
                f"two people together but emotionally distant, tense body language, moody cinematic lighting, {self.subject}",
                f"person alone at night overthinking messages, urban lights blurred in background, realistic, {self.subject}",
                f"mirror reflection showing inner conflict and self-deception, dramatic realism, {self.subject}",
                f"close-up eyes revealing fear, desire, and insecurity, cinematic portrait, {self.subject}",
                f"power dynamic in a conversation, subtle status tension, realistic human behavior, {self.subject}",
                f"isolated figure in a crowded room, emotional disconnection, cinematic realism, {self.subject}",
                f"symbolic scene of attachment and control, grounded realistic style, {self.subject}",
            ]
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
        if self._is_luxury_channel():
            thumb_text = generate_text(
                f"Write a 4-6 word ALL CAPS YouTube thumbnail title for a luxury lifestyle video about: {self.subject}.\n"
                f"Make it rich, bold, exclusive, and curiosity-driven.\n"
                f"Examples: 'INSIDE A BILLIONAIRE LIFE', 'WHAT REAL LUXURY LOOKS LIKE', 'THE OLD MONEY CODE'\n"
                f"Return ONLY the title."
            ).strip().upper()
        else:
            thumb_text = generate_text(
                f"Write a 4-6 word ALL CAPS YouTube thumbnail title for: {self.subject}.\n"
                f"Make it shocking, controversial, or deeply curious.\n"
                f"Examples: 'THE TRUTH THEY HIDE FROM YOU', 'WHAT THEY DON'T TELL YOU'\n"
                f"Return ONLY the title."
            ).strip().upper()
        if len(thumb_text) > 45:
            thumb_text = " ".join(thumb_text.split()[:5])

        # Background image
        if self._is_luxury_channel():
            thumb_prompt = (
                f"Luxury YouTube thumbnail background for a video about {self.subject}. "
                f"Ultra premium black and gold aesthetic, cinematic quality, glossy surfaces, "
                f"wealth, designer interiors, supercars, mansions, no text, high contrast, elite photography."
            )
        else:
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

    def _script_sections(self) -> List[str]:
        sections = []
        for block in re.split(r"\n\s*\n", self.script):
            cleaned = " ".join(line.strip() for line in block.splitlines() if line.strip())
            if cleaned:
                sections.append(cleaned)
        return sections or [self.subject]

    def _estimate_music_only_duration(self, sections: List[str]) -> float:
        word_count = max(1, len(self.script.split()))
        base_duration = max(180.0, min(420.0, word_count * 1.7))
        return max(base_duration, len(sections) * 18.0)

    def _generate_luxury_music(self, duration: float) -> str:
        import subprocess as _sp

        out_path = os.path.join(ROOT_DIR, ".mp", f"lf_luxury_ambient_{uuid4().hex[:6]}.wav")
        expr = (
            "0.45*sin(2*PI*82*t)"
            "+0.22*sin(2*PI*164*t)"
            "+0.14*sin(2*PI*246*t)"
            "+0.08*sin(2*PI*328*t)"
            "+0.05*sin(2*PI*492*t)"
        )
        _sp.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"aevalsrc={expr}:s=44100:d={max(20, int(duration) + 2)}",
                "-af",
                "lowpass=f=5000,highpass=f=40,aecho=0.7:0.8:38|76:0.22|0.14,volume=0.33",
                out_path,
            ],
            check=True,
            timeout=240,
        )
        return out_path

    def _create_text_overlay_image(self, text: str, index: int) -> str:
        canvas = Image.new("RGBA", (1920, 1080), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        panel_y1, panel_y2 = 720, 1040
        draw.rounded_rectangle(
            [(80, panel_y1), (1840, panel_y2)],
            radius=36,
            fill=(0, 0, 0, 170),
            outline=(212, 175, 55, 235),
            width=4,
        )
        draw.rectangle([(80, 735), (1840, 747)], fill=(212, 175, 55, 220))

        font_path = os.path.join(get_fonts_dir(), get_font())
        try:
            title_font = ImageFont.truetype(font_path, 42)
            body_font = ImageFont.truetype(font_path, 58)
        except Exception:
            title_font = ImageFont.load_default()
            body_font = ImageFont.load_default()

        draw.text((120, 765), "BILLIONAIRE PARADISE", font=title_font, fill=(255, 224, 120, 255))

        wrapped = textwrap.wrap(text.upper(), width=34)[:4]
        y = 825
        for line in wrapped:
            bbox = draw.textbbox((0, 0), line, font=body_font)
            line_w = bbox[2] - bbox[0]
            x = (1920 - line_w) // 2
            for dx, dy in [(3, 3), (-3, 3), (3, -3), (-3, -3)]:
                draw.text((x + dx, y + dy), line, font=body_font, fill=(0, 0, 0, 255))
            draw.text((x, y), line, font=body_font, fill=(255, 255, 255, 255))
            y += 68

        out_path = os.path.join(ROOT_DIR, ".mp", f"lf-luxury-overlay-{index}.png")
        canvas.save(out_path)
        return out_path

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

        if self._is_luxury_channel():
            sections = self._script_sections()
            max_duration = self._estimate_music_only_duration(sections)
            per_section = max_duration / max(1, len(sections))
            clips = []
            for idx, section in enumerate(sections):
                img_path = self.images[idx % len(self.images)]
                base_clip = ImageClip(img_path).set_duration(per_section).set_fps(30)
                iw, ih = base_clip.size
                target_ratio = 1920 / 1080
                if iw / ih > target_ratio:
                    new_w = int(ih * target_ratio)
                    base_clip = base_clip.crop(x1=(iw - new_w) // 2, x2=(iw + new_w) // 2)
                else:
                    new_h = int(iw / target_ratio)
                    base_clip = base_clip.crop(y1=(ih - new_h) // 2, y2=(ih + new_h) // 2)
                base_clip = base_clip.resize((1920, 1080))
                zoomed = base_clip.resize(lambda t: 1.0 + 0.04 * (t / max(per_section, 1.0)))
                overlay_path = self._create_text_overlay_image(section, idx)
                overlay_clip = ImageClip(overlay_path).set_duration(per_section).set_position(("center", "center"))
                clips.append(CompositeVideoClip([zoomed, overlay_clip], size=(1920, 1080)))

            final = concatenate_videoclips(clips).set_duration(max_duration)
            music_path = self._generate_luxury_music(max_duration)
            music_clip = AudioFileClip(music_path).set_duration(max_duration).volumex(0.95)
            final = final.set_audio(music_clip)

            vid_path = os.path.join(ROOT_DIR, ".mp", f"lf-video-{uuid4().hex[:8]}.mp4")
            final.write_videofile(vid_path, threads=get_threads(), fps=24, codec="libx264", preset="faster")
            self.video_path = vid_path
            if get_verbose():
                success(f"Long-form luxury video saved: {vid_path}")
            return vid_path

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

        required_scopes = ["https://www.googleapis.com/auth/youtube.upload"]

        token_json = os.environ.get("YOUTUBE_TOKEN_JSON")
        token_info = None
        if token_json:
            token_info = json.loads(token_json)
            creds = Credentials.from_authorized_user_info(token_info)
        else:
            token_path = os.path.join(ROOT_DIR, "token.json")
            if not os.path.exists(token_path):
                raise FileNotFoundError(
                    "token.json not found. Run: python scripts/setup_youtube_auth.py"
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

        if not getattr(creds, "scopes", None):
            creds.scopes = required_scopes

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        return creds

    def upload_video(self) -> str:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
        from utils import run_youtube_resumable_upload
        from utils import format_youtube_http_error

        try:
            creds = self._get_yt_credentials()
            youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

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
            response = run_youtube_resumable_upload(
                request,
                verbose=get_verbose(),
                label="Long-form",
            )

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

        except HttpError as e:
            warning(format_youtube_http_error(e))
            if get_verbose():
                import traceback
                traceback.print_exc()
            return ""
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

        if self._is_luxury_channel():
            info("Skipping TTS for music-only luxury video...")
        else:
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
