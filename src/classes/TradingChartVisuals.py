import math
import os
from datetime import datetime
from typing import Iterable, List

import requests
from PIL import Image, ImageDraw, ImageFont

from config import ROOT_DIR, get_font, get_fonts_dir, get_verbose
from status import warning


DEFAULT_SYMBOLS = ["SPY", "QQQ", "AAPL", "MSFT", "BTC-USD", "ETH-USD"]


def _font(size: int):
    path = os.path.join(get_fonts_dir(), get_font())
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _fetch_yahoo_candles(symbol: str, *, range_: str = "6mo", interval: str = "1d") -> List[dict]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
    response = requests.get(
        url,
        params={"range": range_, "interval": interval},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    result = body.get("chart", {}).get("result", [])
    if not result:
        return []
    item = result[0]
    timestamps = item.get("timestamp") or []
    quote = (item.get("indicators", {}).get("quote") or [{}])[0]
    candles = []
    for idx, ts in enumerate(timestamps):
        try:
            open_ = float(quote["open"][idx])
            high = float(quote["high"][idx])
            low = float(quote["low"][idx])
            close = float(quote["close"][idx])
        except Exception:
            continue
        if any(math.isnan(v) for v in [open_, high, low, close]):
            continue
        candles.append(
            {
                "date": datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d"),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
            }
        )
    return candles


def _fallback_candles(count: int = 90) -> List[dict]:
    candles = []
    price = 100.0
    for idx in range(count):
        drift = math.sin(idx / 7.0) * 0.8 + math.cos(idx / 13.0) * 0.45
        open_ = price
        close = max(40, open_ + drift)
        high = max(open_, close) + 0.9 + abs(math.sin(idx)) * 0.7
        low = min(open_, close) - 0.9 - abs(math.cos(idx)) * 0.7
        price = close
        candles.append(
            {
                "date": f"demo-{idx + 1:03d}",
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
            }
        )
    return candles


def fetch_real_candles(symbols: Iterable[str] = DEFAULT_SYMBOLS) -> tuple[str, List[dict], bool]:
    for symbol in symbols:
        try:
            candles = _fetch_yahoo_candles(symbol)
            if len(candles) >= 40:
                return symbol, candles[-90:], True
        except Exception as exc:
            if get_verbose():
                warning(f"Real chart fetch failed for {symbol}: {exc}")
    return "DEMO", _fallback_candles(), False


def _subject_labels(subject: str) -> tuple[str, str, str]:
    text = subject.lower()
    if "doji" in text:
        return "DOJI", "Indecision candle", "Small body shows buyers and sellers fought to a draw."
    if "hammer" in text:
        return "HAMMER", "Rejection candle", "Long lower wick shows sellers pushed down, then buyers fought back."
    if "engulf" in text:
        return "ENGULFING", "Momentum shift", "A larger candle can show one side taking control."
    if "support" in text:
        return "SUPPORT", "Demand zone", "Price reacted here before, so beginners watch the retest."
    if "resistance" in text:
        return "RESISTANCE", "Supply zone", "Repeated rejection means buyers need strength to break through."
    if "breakout" in text:
        return "BREAKOUT", "Range break", "A move outside the range matters more when volume expands."
    if "fakeout" in text:
        return "FAKEOUT", "Failed break", "Price breaks a level, traps traders, then returns inside."
    if "trend" in text:
        return "TREND", "Market direction", "Higher highs and higher lows show buyers still control the move."
    if "risk" in text or "stop" in text:
        return "RISK", "Invalidation first", "A chart setup is incomplete until you know where you are wrong."
    return "CANDLESTICKS", "Price action lesson", "Each candle shows the battle between buyers and sellers."


def _scale(value: float, low: float, high: float, top: int, bottom: int) -> int:
    if high <= low:
        return (top + bottom) // 2
    return int(bottom - ((value - low) / (high - low)) * (bottom - top))


def _draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font, fill, max_width: int, line_gap: int = 8):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textbbox((0, 0), test, font=font)[2] <= max_width or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    x, y = xy
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap if hasattr(font, "size") else 28


def draw_chart_frame(
    candles: List[dict],
    *,
    subject: str,
    symbol: str,
    real_data: bool,
    output_path: str,
    size: tuple[int, int] = (1920, 1080),
    reveal_ratio: float = 1.0,
    vertical: bool = False,
) -> str:
    width, height = size
    img = Image.new("RGB", size, (8, 12, 18))
    draw = ImageDraw.Draw(img)

    title, subtitle, note = _subject_labels(subject)
    accent = (56, 189, 248)
    green = (34, 197, 94)
    red = (248, 113, 113)
    muted = (148, 163, 184)
    white = (241, 245, 249)
    grid = (30, 41, 59)

    margin_x = 72 if vertical else 110
    top = 170 if vertical else 140
    bottom = height - (300 if vertical else 190)
    chart_right = width - margin_x
    chart_left = margin_x

    visible_count = max(20, int(len(candles) * max(0.25, min(1.0, reveal_ratio))))
    visible = candles[-visible_count:]
    lows = [c["low"] for c in visible]
    highs = [c["high"] for c in visible]
    low = min(lows)
    high = max(highs)
    pad = (high - low) * 0.08 or 1.0
    low -= pad
    high += pad

    for i in range(6):
        y = top + int((bottom - top) * i / 5)
        draw.line((chart_left, y, chart_right, y), fill=grid, width=1)
        price = high - (high - low) * i / 5
        draw.text((chart_right - 90, y - 24), f"{price:.2f}", fill=muted, font=_font(22 if vertical else 24))

    candle_gap = 4 if vertical else 5
    slot = (chart_right - chart_left) / max(1, len(visible))
    body_w = max(5, int(slot * 0.58) - candle_gap)

    for idx, candle in enumerate(visible):
        x = int(chart_left + idx * slot + slot / 2)
        y_high = _scale(candle["high"], low, high, top, bottom)
        y_low = _scale(candle["low"], low, high, top, bottom)
        y_open = _scale(candle["open"], low, high, top, bottom)
        y_close = _scale(candle["close"], low, high, top, bottom)
        color = green if candle["close"] >= candle["open"] else red
        draw.line((x, y_high, x, y_low), fill=color, width=3 if vertical else 4)
        y1, y2 = sorted([y_open, y_close])
        if y2 - y1 < 3:
            y2 = y1 + 3
        draw.rounded_rectangle((x - body_w // 2, y1, x + body_w // 2, y2), radius=2, fill=color)

    if visible:
        last = visible[-1]
        last_y = _scale(last["close"], low, high, top, bottom)
        draw.line((chart_left, last_y, chart_right, last_y), fill=(71, 85, 105), width=2)
        draw.rounded_rectangle((chart_right - 140, last_y - 24, chart_right - 10, last_y + 24), radius=8, fill=(15, 23, 42))
        draw.text((chart_right - 128, last_y - 17), f"{last['close']:.2f}", fill=white, font=_font(24))

    level_y = _scale(sum(c["close"] for c in visible[-12:]) / min(12, len(visible)), low, high, top, bottom)
    draw.line((chart_left, level_y, chart_right, level_y), fill=accent, width=3)
    draw.text((chart_left + 8, level_y - 36), "key level", fill=accent, font=_font(24 if vertical else 28))

    draw.text((margin_x, 38), title, fill=white, font=_font(76 if vertical else 70))
    draw.text((margin_x, 112), subtitle, fill=accent, font=_font(34 if vertical else 36))
    data_label = f"{symbol} real market candles" if real_data else "offline demo candles"
    draw.text((chart_right - 330, 48), data_label, fill=muted, font=_font(24 if vertical else 26))

    panel_y = bottom + 35
    draw.rounded_rectangle((margin_x, panel_y, chart_right, height - 42), radius=22, fill=(15, 23, 42), outline=(51, 65, 85), width=2)
    _draw_wrapped(draw, (margin_x + 32, panel_y + 26), note, _font(32 if vertical else 36), white, chart_right - margin_x - 64)
    _draw_wrapped(
        draw,
        (margin_x + 32, panel_y + 148 if vertical else panel_y + 78),
        "Educational only. This is not financial advice or a trade signal.",
        _font(23 if vertical else 24),
        muted,
        chart_right - margin_x - 64,
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, "JPEG", quality=94)
    return output_path


def generate_chart_story_images(subject: str, *, count: int, vertical: bool = False) -> List[str]:
    symbol, candles, real_data = fetch_real_candles()
    size = (1080, 1920) if vertical else (1920, 1080)
    paths = []
    for idx in range(count):
        reveal = 0.35 + (idx / max(1, count - 1)) * 0.65
        path = os.path.join(ROOT_DIR, ".mp", f"trading-chart-{idx + 1:02d}.jpg")
        paths.append(
            draw_chart_frame(
                candles,
                subject=subject,
                symbol=symbol,
                real_data=real_data,
                output_path=path,
                size=size,
                reveal_ratio=reveal,
                vertical=vertical,
            )
        )
    return paths
