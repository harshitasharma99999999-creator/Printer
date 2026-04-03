import os
import re
import time
import requests

from llm_provider import generate_text
from config import ROOT_DIR, get_verbose, get_gumroad_access_token
from status import info, warning, success


TYPES = [
    "daily habit tracker",
    "weekly reflection journal",
    "shadow work journal",
    "morning routine planner",
    "gratitude journal",
    "goal setting worksheet",
    "affirmation card set",
]


class Printables:
    """
    Generates printable PDFs (habit trackers, journals, worksheets)
    and lists them on Gumroad automatically.
    Runs weekly (every Monday) via distributor_runner.py.
    """

    def _generate_prompts(self, printable_type: str, topic: str) -> list:
        prompt = (
            f"Create a beautiful printable {printable_type} about: {topic}\n"
            f"Generate exactly 10 deep, introspective prompts/items for this printable.\n"
            f"Each item should draw from Jungian psychology, shadow work, or self-discovery.\n"
            f"Return as a numbered list 1-10. No explanations, just the prompts."
        )
        raw = generate_text(prompt).strip()
        items = []
        for line in raw.splitlines():
            m = re.match(r"^\d+[\.\)]\s*(.+)", line.strip())
            if m:
                items.append(m.group(1).strip())
        if len(items) < 5:
            items = [f"Prompt {i + 1} about {topic}" for i in range(10)]
        return items[:10]

    def generate_pdf(self, printable_type: str, topic: str) -> str:
        """Generate printable PDF with ReportLab. Returns file path."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.enums import TA_CENTER, TA_LEFT

        items = self._generate_prompts(printable_type, topic)

        slug = re.sub(r"[^a-z0-9]", "-", printable_type.lower())
        path = os.path.join(ROOT_DIR, ".mp", f"printable-{slug}.pdf")

        doc = SimpleDocTemplate(
            path, pagesize=A4,
            rightMargin=inch, leftMargin=inch,
            topMargin=inch, bottomMargin=inch,
        )

        styles = getSampleStyleSheet()
        dark = HexColor("#1a1a2e")
        gold = HexColor("#c4a44d")
        grey = HexColor("#888888")

        title_s = ParagraphStyle("PT", parent=styles["Title"], fontSize=24, textColor=dark,
                                  alignment=TA_CENTER, spaceAfter=8)
        sub_s = ParagraphStyle("PS", parent=styles["Normal"], fontSize=12, textColor=gold,
                                alignment=TA_CENTER, spaceAfter=28)
        label_s = ParagraphStyle("PL", parent=styles["Normal"], fontSize=11, textColor=dark,
                                  spaceBefore=18, spaceAfter=6, fontName="Helvetica-Bold")
        line_s = ParagraphStyle("LN", parent=styles["Normal"], fontSize=9, textColor=grey,
                                 spaceAfter=3, alignment=TA_LEFT)

        story = []
        story.append(Spacer(1, 0.4 * inch))
        story.append(Paragraph(printable_type.title(), title_s))
        story.append(Paragraph(f"A Jungian {topic} Practice", sub_s))

        for i, item in enumerate(items, 1):
            story.append(Paragraph(f"{i}. {item}", label_s))
            for _ in range(4):
                story.append(Paragraph("_" * 65, line_s))
            story.append(Spacer(1, 0.05 * inch))

        doc.build(story)

        if get_verbose():
            info(f"Printables: PDF saved → {path}")
        return path

    def list_on_gumroad(self, printable_type: str, topic: str, pdf_path: str) -> str:
        """List printable on Gumroad. Returns URL."""
        access_token = (
            os.environ.get("GUMROAD_ACCESS_TOKEN", "").strip()
            or get_gumroad_access_token()
        )
        if not access_token:
            if get_verbose():
                warning("Printables: GUMROAD_ACCESS_TOKEN not set.")
            return ""

        title = f"{printable_type.title()}: {topic}"[:100]
        description = (
            f"A deep, introspective {printable_type} inspired by Jungian psychology. "
            f"Perfect for shadow work, self-reflection, and personal growth. "
            f"Instant PDF download — 10 thoughtful prompts with writing space."
        )

        base = "https://api.gumroad.com/v2"
        r = requests.post(f"{base}/products", data={
            "access_token": access_token,
            "name": title,
            "price": 299,  # $2.99
            "description": description,
        }, timeout=20)

        if not r.ok:
            if get_verbose():
                warning(f"Printables: Gumroad create failed {r.status_code}")
            return ""

        product = r.json().get("product", {})
        product_id = product.get("id", "")
        product_url = product.get("short_url", f"https://app.gumroad.com/products/{product_id}")

        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                requests.post(
                    f"{base}/products/{product_id}/product_files",
                    data={"access_token": access_token},
                    files={"file": (os.path.basename(pdf_path), f, "application/pdf")},
                    timeout=60,
                )

        requests.put(f"{base}/products/{product_id}", data={
            "access_token": access_token, "published": "true",
        }, timeout=15)

        if get_verbose():
            success(f"Printables: Gumroad live → {product_url}")
        return product_url

    def run(self, topic: str) -> str:
        """Pick printable type, generate PDF, list on Gumroad."""
        printable_type = TYPES[int(time.time()) % len(TYPES)]
        if get_verbose():
            info(f"Printables: generating '{printable_type}' for topic '{topic}'")
        pdf_path = self.generate_pdf(printable_type, topic)
        return self.list_on_gumroad(printable_type, topic, pdf_path)
