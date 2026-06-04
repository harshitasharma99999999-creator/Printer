import json
import os
import re
from typing import List
from uuid import uuid4

from config import ROOT_DIR, get_script_sentence_length, get_threads, get_verbose
from llm_provider import generate_text
from status import error, info, success, warning

from .TradingChartVisuals import generate_chart_story_images
from .YouTube import YouTube


TRADING_SHORTS_NICHE = (
    "trading education from scratch beginner trading course risk management "
    "technical analysis chart reading support resistance candlesticks trading psychology paper trading"
)


class TradingShorts(YouTube):
    """Tradingclub-specific Shorts generator for daily beginner lessons."""

    def _is_trading_education_channel(self) -> bool:
        return True

    def generate_topic(self) -> str:
        completion = self.generate_response(
            f"""Generate one premium YouTube Shorts lesson topic for @Tradingclub-q7u.
Audience: complete beginners learning trading from scratch.
Style: clear, practical, A-to-Z trading education in tiny daily lessons.
Use formats like:
- "Trading vs Investing Explained In 30 Seconds"
- "What Bid And Ask Mean For Beginners"
- "The Stop Loss Rule Beginners Must Learn"
- "Why Position Size Matters More Than Being Right"
- "How Support And Resistance Actually Work"
- "The Difference Between Breakout And Fakeout"
- "Why Most Beginners Overtrade"
- "How A Doji Candle Shows Indecision"
- "Bullish Engulfing Explained On A Real Chart"
- "What A Hammer Candle Actually Means"
- "Double Top Pattern Explained Simply"
Rules:
- Teach one beginner concept only
- Prefer candlesticks, price action, chart patterns, support, resistance, or risk lessons
- No live trade calls, no price predictions, no profit promises
- Make it useful, simple, and curiosity-driven
- Return ONLY the topic as one sentence
- No emojis, no numbering, nothing else

Niche: {self.niche}"""
        )
        if not completion:
            error("Failed to generate Topic.")
        self.subject = completion.strip().strip('"').strip("'")
        return self.subject

    def generate_script(self) -> str:
        sentence_length = get_script_sentence_length()
        prompt = f"""You are the educator for @Tradingclub-q7u, a premium trading channel teaching complete beginners from scratch.
Write a script of exactly {sentence_length} sentences about the subject below.

Tone:
- Clear, calm, practical, and top-level educational
- Start with a simple hook that removes beginner confusion
- Explain one concept from first principles
- Use plain English first, then the correct trading term
- Include one tiny example or rule the viewer can remember
- End with a useful takeaway or practice step

Rules:
- Exactly {sentence_length} sentences
- NO markdown, NO titles, NO bullet points
- NO filler like "in this video"
- No financial advice, no buy/sell signals, no price predictions, no profit promises
- Mention risk naturally when relevant
- Spoken words only
- Language: {self.language}

Subject: {self.subject}"""
        completion = self.generate_response(prompt)
        completion = re.sub(r"\*", "", completion or "").strip()
        if not completion:
            error("The generated script is empty.")
            return ""
        if len(completion) > 5000:
            if get_verbose():
                warning("Generated Script is too long. Retrying...")
            return self.generate_script()
        self.script = completion
        return completion

    @staticmethod
    def _clean_text(text: str, limit: int) -> str:
        text = re.sub(r"[\x00-\x1F\x7F]", "", str(text or ""))
        text = re.sub(r"[ \t]+", " ", text).strip()
        return text[:limit]

    def generate_metadata(self) -> dict:
        title = self.generate_response(
            f"""Generate a YouTube Shorts title for a beginner trading education lesson.
Channel: @Tradingclub-q7u
Subject: {self.subject}
Style: clear, useful, premium, and beginner-friendly.
Use formats like:
"Trading Basics: X Explained", "Learn Trading: X", "The X Rule Beginners Need", "X Explained For Beginners"
Rules:
- Under 100 characters
- No profit promises
- No price predictions
- Return only the title"""
        ).strip().strip('"').strip("'")
        if len(title) > 100:
            title = title[:97] + "..."

        summary = self.generate_response(
            f"Write one short YouTube Shorts description sentence for this beginner trading lesson: {self.subject}. "
            f"Make it educational and calm. No markdown. No financial advice. No profit promises."
        )
        summary = self._clean_text(summary, 220)
        if not summary:
            summary = "A simple beginner trading lesson from Tradingclub's A-to-Z trading roadmap."

        description = (
            f"{self._clean_text(self.subject, 120)}\n\n"
            f"{summary}\n\n"
            "Educational only. Trading involves risk. Practice before risking real capital.\n\n"
            "Subscribe to Tradingclub for daily A-to-Z trading lessons from scratch.\n"
            "Not financial advice.\n\n"
            "#Shorts #TradingForBeginners #LearnTrading #TradingEducation #RiskManagement"
        )

        self.metadata = {
            "title": self._clean_text(title, 100),
            "description": description[:5000],
            "tags": [
                "trading for beginners",
                "learn trading",
                "trading education",
                "trading from scratch",
                "technical analysis",
                "risk management",
                "stock trading",
                "forex trading",
                "crypto trading",
                "trading psychology",
                "paper trading",
                "beginner trading course",
                "Tradingclub",
                "shorts",
            ],
        }
        return self.metadata

    def generate_prompts(self, _retries: int = 0) -> List[str]:
        n_prompts = 5
        prompt = f"""Generate exactly {n_prompts} cinematic vertical image prompts for a YouTube Short beginner trading lesson.
Each image must feel premium, clear, educational, and beginner-friendly, showing clean chart screens, trading notebooks, risk plans, simple market diagrams, paper trading practice, and calm learning environments.
Style: modern trading education visuals, dark studio, clean blue and green accents, realistic screens, professional desk, clear chart shapes, premium lighting.
DO NOT generate fantasy art, cartoons, fake logos, profit claims, luxury flex, or unreadable text-heavy images.
Return ONLY a JSON array of {n_prompts} strings, nothing else.

Subject: {self.subject}"""
        try:
            response = generate_text(prompt)
            match = re.search(r"\[.*\]", response, re.DOTALL)
            if not match:
                raise ValueError("No JSON array found")
            image_prompts = json.loads(match.group(0))
            if not isinstance(image_prompts, list) or not image_prompts:
                raise ValueError("Invalid prompt list")
            image_prompts = [str(p).strip() for p in image_prompts[:n_prompts] if str(p).strip()]
        except Exception:
            if _retries < 3:
                if get_verbose():
                    warning("Failed to parse image prompts. Retrying...")
                return self.generate_prompts(_retries=_retries + 1)
            image_prompts = [
                f"modern trading education desk with clean candlestick chart screens and a beginner risk notebook, blue green accent lighting, {self.subject}",
                f"close-up of paper trading journal beside laptop chart, calm beginner learning mood, premium dark studio, {self.subject}",
                f"simple market structure diagram on a clean screen with professional trading classroom atmosphere, no readable text, {self.subject}",
                f"beginner trader calmly studying charts with risk management notes, realistic cinematic lighting, {self.subject}",
                f"organized trading workstation with calculator, notebook, and clean market dashboard, educational and premium, {self.subject}",
            ]

        self.image_prompts = image_prompts
        if get_verbose():
            info(f" => Generated Image Prompts: {image_prompts}")
        success(f"Generated {len(image_prompts)} Image Prompts.")
        return image_prompts

    def generate_video(self, tts_instance) -> str:
        try:
            if not hasattr(self, "subject") or not self.subject:
                self.generate_topic()

            self.generate_script()
            self.generate_metadata()

            info("Generating real chart visuals for Tradingclub Short...")
            self.images = generate_chart_story_images(self.subject, count=5, vertical=True)

            self.generate_script_to_speech(tts_instance)
            path = self.combine()
            self.video_path = path
            return path
        except Exception as exc:
            error(f"Tradingclub Short generation failed: {exc}")
            raise

    def combine(self) -> str:
        from moviepy.editor import AudioFileClip, ImageClip, concatenate_videoclips

        if not self.images:
            raise RuntimeError("No chart images were generated for the Tradingclub Short.")

        audio = AudioFileClip(self.tts_path)
        duration = audio.duration
        per_image = duration / max(1, len(self.images))
        clips = []
        for image_path in self.images:
            clip = ImageClip(image_path).set_duration(per_image).set_fps(30)
            if clip.size != (1080, 1920):
                clip = clip.resize((1080, 1920))
            clips.append(clip)

        final = concatenate_videoclips(clips).set_duration(duration).set_audio(audio)
        out_path = os.path.join(ROOT_DIR, ".mp", f"trading-short-{uuid4().hex[:8]}.mp4")
        final.write_videofile(
            out_path,
            threads=get_threads(),
            fps=30,
            codec="libx264",
            audio_codec="aac",
            preset="faster",
        )
        self.video_path = out_path
        success(f'Wrote Tradingclub Short to "{out_path}"')
        return out_path
