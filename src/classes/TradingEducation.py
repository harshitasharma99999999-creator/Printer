import json
import os
import re
from datetime import datetime
from typing import List

from cache import get_cache_path
from config import ROOT_DIR, get_verbose
from llm_provider import generate_text
from status import info

from .TradingChartVisuals import generate_chart_story_images
from .LongForm import LongForm


TRADING_EDUCATION_NICHE = "trading education from scratch for complete beginners"

TRADING_CURRICULUM = [
    {
        "module": "Trading Foundations",
        "lessons": [
            "What trading is and how it differs from investing",
            "How financial markets actually work",
            "Stocks, forex, crypto, commodities, and indices explained",
            "Market participants: retail traders, institutions, market makers, and algorithms",
            "Bid, ask, spread, liquidity, volume, and slippage",
            "Order types: market orders, limit orders, stop orders, and stop-limit orders",
        ],
    },
    {
        "module": "Risk First",
        "lessons": [
            "Why risk management matters more than prediction",
            "Position sizing explained with simple examples",
            "Stop losses, invalidation, and protecting capital",
            "Risk to reward ratio and expectancy",
            "Drawdowns, losing streaks, and survival rules",
            "The difference between gambling and professional risk taking",
        ],
    },
    {
        "module": "Chart Reading",
        "lessons": [
            "Candlesticks explained for absolute beginners",
            "Trends, ranges, support, and resistance",
            "Breakouts, fakeouts, and retests",
            "Multiple time frame analysis",
            "Volume analysis and why price needs participation",
            "Market structure: higher highs, lower lows, and trend changes",
        ],
    },
    {
        "module": "Candlestick Masterclass",
        "lessons": [
            "How one candlestick shows open, high, low, and close",
            "Bullish candles and bearish candles explained on real charts",
            "Wicks explained: rejection, liquidity, and failed moves",
            "Doji candles and market indecision",
            "Hammer candles and why context matters",
            "Shooting star candles and rejection at resistance",
            "Bullish engulfing candles with real chart movement",
            "Bearish engulfing candles with real chart movement",
            "Inside bars, outside bars, and compression",
            "Why candlestick patterns fail without trend and level context",
        ],
    },
    {
        "module": "Chart Patterns With Real Movement",
        "lessons": [
            "Double tops and double bottoms explained on real charts",
            "Head and shoulders pattern explained step by step",
            "Triangles, compression, and breakout pressure",
            "Flags and pullbacks inside trending markets",
            "Cup and handle pattern without beginner hype",
            "Breakout, retest, and continuation explained",
            "Fakeouts and liquidity grabs on real chart movement",
            "Support and resistance flips explained visually",
            "Trendlines, channels, and when they stop working",
            "How to read patterns without predicting the future",
        ],
    },
    {
        "module": "Technical Tools",
        "lessons": [
            "Moving averages and trend context",
            "RSI, momentum, and overbought or oversold myths",
            "VWAP and institutional price context",
            "Fibonacci retracements without magic thinking",
            "Chart patterns that beginners misunderstand",
            "How to combine indicators without clutter",
        ],
    },
    {
        "module": "Fundamental And Macro Context",
        "lessons": [
            "What moves stocks, currencies, crypto, and commodities",
            "Interest rates, inflation, and central banks explained",
            "Earnings, guidance, and valuation basics",
            "Economic calendars and major news events",
            "Sentiment, positioning, and narrative cycles",
            "When fundamentals matter and when charts lead",
        ],
    },
    {
        "module": "Strategy Building",
        "lessons": [
            "How to build a simple trading plan",
            "Entry triggers, invalidation, targets, and management",
            "Backtesting basics without fooling yourself",
            "Forward testing and paper trading",
            "Creating rules for trend, range, and news conditions",
            "How to know when a strategy is not working",
        ],
    },
    {
        "module": "Trading Psychology",
        "lessons": [
            "Fear, greed, FOMO, revenge trading, and hesitation",
            "Why discipline fails without systems",
            "How to handle losses like a professional",
            "Journaling trades to find your real weaknesses",
            "Building patience and waiting for your setup",
            "The mindset shift from prediction to probability",
        ],
    },
    {
        "module": "Advanced Beginner Roadmap",
        "lessons": [
            "Portfolio risk and correlation",
            "Leverage, margin, liquidation, and why beginners get trapped",
            "Options and derivatives explained safely",
            "Taxes, fees, and hidden costs traders ignore",
            "Creating a weekly market preparation routine",
            "A complete beginner-to-consistent-trader roadmap",
        ],
    },
]


class TradingEducation(LongForm):
    """
    Curriculum-driven long-form YouTube automation for a beginner trading channel.

    The class advances lesson-by-lesson through a stored curriculum so uploads
    build a coherent course instead of isolated market commentary.
    """

    def __init__(
        self,
        account_uuid: str,
        account_nickname: str,
        fp_profile_path: str,
        niche: str,
        language: str,
    ) -> None:
        super().__init__(
            account_uuid,
            account_nickname,
            fp_profile_path,
            niche or TRADING_EDUCATION_NICHE,
            language,
        )
        self.channel_handle = "@Tradingclub-q7u"
        self.lesson: dict = {}

    @staticmethod
    def _progress_path() -> str:
        return os.path.join(get_cache_path(), "trading_curriculum.json")

    @classmethod
    def _flat_curriculum(cls) -> List[dict]:
        lessons = []
        lesson_number = 1
        for module_number, module in enumerate(TRADING_CURRICULUM, 1):
            for lesson_title in module["lessons"]:
                lessons.append(
                    {
                        "lesson_number": lesson_number,
                        "module_number": module_number,
                        "module": module["module"],
                        "title": lesson_title,
                    }
                )
                lesson_number += 1
        return lessons

    @classmethod
    def curriculum_summary(cls) -> str:
        lines = []
        for module_number, module in enumerate(TRADING_CURRICULUM, 1):
            lines.append(f"{module_number}. {module['module']}")
            for lesson in module["lessons"]:
                lines.append(f"   - {lesson}")
        return "\n".join(lines)

    @classmethod
    def peek_next_lesson(cls) -> dict:
        lessons = cls._flat_curriculum()
        idx = cls._read_progress().get("next_lesson_index", 0)
        return lessons[idx % len(lessons)]

    @classmethod
    def _read_progress(cls) -> dict:
        path = cls._progress_path()
        if not os.path.exists(path):
            return {"next_lesson_index": 0, "completed": []}
        try:
            with open(path, "r", encoding="utf-8") as file:
                data = json.load(file)
            if isinstance(data, dict):
                data.setdefault("next_lesson_index", 0)
                data.setdefault("completed", [])
                return data
        except Exception:
            pass
        return {"next_lesson_index": 0, "completed": []}

    @classmethod
    def _write_progress(cls, progress: dict) -> None:
        os.makedirs(get_cache_path(), exist_ok=True)
        with open(cls._progress_path(), "w", encoding="utf-8") as file:
            json.dump(progress, file, indent=4)

    @classmethod
    def reset_progress(cls) -> None:
        cls._write_progress({"next_lesson_index": 0, "completed": []})

    def _select_next_lesson(self) -> dict:
        lessons = self._flat_curriculum()
        progress = self._read_progress()
        idx = int(progress.get("next_lesson_index", 0)) % len(lessons)
        self.lesson = lessons[idx]
        return self.lesson

    def _mark_lesson_complete(self, result: dict) -> None:
        progress = self._read_progress()
        completed = progress.get("completed", [])
        completed.append(
            {
                "lesson_number": self.lesson.get("lesson_number"),
                "module": self.lesson.get("module"),
                "title": self.lesson.get("title"),
                "url": result.get("url", ""),
                "video_path": result.get("video_path", ""),
                "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        progress["completed"] = completed
        progress["next_lesson_index"] = int(progress.get("next_lesson_index", 0)) + 1
        self._write_progress(progress)

    def generate_topic(self) -> str:
        lesson = self._select_next_lesson()
        self.subject = (
            f"Lesson {lesson['lesson_number']}: {lesson['title']} "
            f"({lesson['module']})"
        )
        return self.subject

    def generate_script(self) -> str:
        lesson = self.lesson or self._select_next_lesson()
        title = lesson["title"]
        module = lesson["module"]
        lesson_number = lesson["lesson_number"]

        prompt = f"""You are the lead educator for {self.channel_handle}, a premium YouTube channel teaching trading from absolute zero.
Write a complete 10-15 minute beginner trading lesson.

Lesson:
- Course lesson number: {lesson_number}
- Module: {module}
- Topic: {title}

Teaching standard:
- Explain from first principles for an ultimate beginner who knows nothing.
- Use simple analogies, then precise trading terms.
- Teach what it is, why it matters, how it works, common beginner mistakes, and a practical exercise.
- Be accurate, calm, structured, and professional.
- Make it educational, not hype.
- Include risk warnings naturally: no guaranteed profits, trading can lose money, practice before risking capital.
- Do not give live financial advice, buy/sell signals, price predictions, or promises.
- Avoid fake guru language.

Required spoken structure:
1. A strong hook that makes the beginner feel this lesson removes confusion.
2. A clear explanation of the concept in plain English.
3. A realistic example using simple numbers where useful.
4. Mistakes beginners make and how to avoid them.
5. A practical homework exercise the viewer can do on a demo chart or paper trading journal.
6. A concise recap and a clean subscribe line for the next lesson.

Rules:
- No markdown, no headings, no bullet points, no numbered list formatting.
- Spoken narration only.
- Use short paragraphs separated by blank lines.
- Language: {self.language}.
"""
        raw = generate_text(prompt).strip()
        script = self._clean_script(raw)
        if len(script.split()) < 900:
            expansion = generate_text(
                f"Expand this beginner trading lesson to be more complete while keeping it spoken narration only. "
                f"Add clearer examples, beginner mistakes, and a practical homework exercise. No markdown.\n\n{script}"
            ).strip()
            script = self._clean_script(expansion)
        self.script = script
        return self.script

    def generate_metadata(self) -> dict:
        lesson = self.lesson or self._select_next_lesson()
        title = generate_text(
            f"Write a YouTube title for a premium beginner trading course lesson.\n"
            f"Course: Trading From Scratch\n"
            f"Lesson {lesson['lesson_number']}: {lesson['title']}\n"
            f"Make it clear, educational, SEO-friendly, and under 70 characters.\n"
            f"Return only the title, no quotes."
        ).strip().strip('"').strip("'")
        if not title:
            title = f"Trading From Scratch: {lesson['title']}"
        if len(title) > 100:
            title = title[:97] + "..."

        description = (
            f"Trading From Scratch - Lesson {lesson['lesson_number']}: {lesson['title']}\n\n"
            f"In this {self.channel_handle} lesson, we teach {lesson['title'].lower()} from the ground up for complete beginners. "
            f"You will learn the concept, why it matters, how beginners should think about it, the mistakes to avoid, "
            f"and a practical exercise to build real skill step by step.\n\n"
            f"This channel is educational only. Trading involves risk, and you can lose money. "
            f"Nothing in this video is financial advice, a signal, or a promise of profit. "
            f"Practice with a demo account or paper journal before risking real capital.\n\n"
            f"Course module: {lesson['module']}\n"
            f"Next lessons continue the full A-to-Z trading roadmap for beginners.\n\n"
            f"#TradingForBeginners #TradingEducation #TechnicalAnalysis #RiskManagement #TradingPsychology"
        )

        self.metadata = {
            "title": title,
            "description": description,
            "tags": [
                "trading for beginners",
                "trading from scratch",
                "learn trading",
                "technical analysis",
                "risk management",
                "stock trading",
                "forex trading",
                "crypto trading",
                "trading psychology",
                "paper trading",
                "beginner trading course",
                "Tradingclub",
            ],
        }
        return self.metadata

    def generate_image_prompts(self) -> List[str]:
        lesson = self.lesson or self._select_next_lesson()
        raw = generate_text(
            f"Generate 8 cinematic 16:9 image prompts for a premium trading education YouTube lesson.\n"
            f"Lesson: {lesson['title']}\n"
            f"Module: {lesson['module']}\n"
            f"Style: realistic modern trading desk, clean charts, risk notebook, market screens, classroom whiteboard, professional educator, "
            f"beginner-friendly financial learning, premium dark studio, blue and green accent lighting. "
            f"No text inside images, no fake logos, no profit claims, no luxury flex.\n"
            f"Return JSON array of 8 strings only."
        ).strip()
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            try:
                prompts = json.loads(match.group(0))
                if isinstance(prompts, list) and prompts:
                    return [str(prompt) for prompt in prompts[:8]]
            except Exception:
                pass
        return [
            f"premium trading education studio with clean market charts on screens, beginner lesson about {lesson['title']}, cinematic 16:9, no text",
            f"close-up of a trader writing risk notes in a journal beside a simple candlestick chart, {lesson['title']}, realistic, no text",
            f"modern classroom whiteboard with blank chart shapes and professional teacher silhouette, trading education, no readable text",
            f"clean financial market dashboard on monitors with soft blue and green lighting, beginner trading concept {lesson['title']}, no text",
            f"paper trading practice setup with notebook, calculator, and laptop chart, realistic premium lighting, no text",
            f"calm beginner trader studying charts without stress, professional home office, educational mood, no text",
            f"abstract but realistic visualization of market structure and risk control using charts and light trails, no words",
            f"wide shot of a professional trading desk built for learning, organized screens, risk journal, no text",
        ]

    def generate_images(self) -> List[str]:
        lesson = self.lesson or self._select_next_lesson()
        info("Generating real chart visuals (16:9)...")
        self.images = generate_chart_story_images(
            f"{lesson['title']} - {lesson['module']}",
            count=10,
            vertical=False,
        )
        return self.images

    def generate_thumbnail(self) -> str:
        lesson = self.lesson or self._select_next_lesson()
        thumb_text = generate_text(
            f"Write a 3-5 word ALL CAPS thumbnail title for this beginner trading lesson: {lesson['title']}.\n"
            f"Make it clear, educational, and curiosity-driven without hype or profit promises.\n"
            f"Examples: LEARN TRADING BASICS, RISK BEFORE PROFITS, READ CHARTS FAST\n"
            f"Return only the words."
        ).strip().upper()
        if not thumb_text:
            thumb_text = "TRADING FROM SCRATCH"
        if len(thumb_text) > 45:
            thumb_text = " ".join(thumb_text.split()[:5])

        thumb_prompt = (
            f"Premium YouTube thumbnail background for a beginner trading course lesson about {lesson['title']}. "
            f"Clean trading desk, chart screens, confident educational mood, dark studio, blue and green accents, "
            f"professional finance education, no text, no logos, no profit claims."
        )
        bg_path = self._generate_image_gemini(thumb_prompt, aspect="16:9")
        if not bg_path and self.images:
            bg_path = self.images[0]
        if not bg_path:
            return ""
        self.thumbnail_path = self._add_thumbnail_text(bg_path, thumb_text)
        return self.thumbnail_path

    def run(self) -> dict:
        result = super().run()
        self._mark_lesson_complete(result)
        if get_verbose():
            info(f"Trading curriculum advanced after lesson {self.lesson.get('lesson_number')}.")
        return result
