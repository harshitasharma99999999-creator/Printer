import os
import re
import requests

from llm_provider import generate_text
from config import ROOT_DIR, get_verbose, get_gumroad_access_token
from status import info, warning, success


class Course:
    """
    Generates a 10-lesson PDF course and lists it on Gumroad.
    Runs monthly (1st of each month) via distributor_runner.py.
    Price: $19.97 — highest-value product in the funnel.
    """

    def _generate_lesson(self, lesson_title: str, course_topic: str, lesson_num: int) -> str:
        prompt = (
            f"Write Lesson {lesson_num} of a psychology course: '{lesson_title}'\n"
            f"Course topic: {course_topic}\n"
            f"Write 5 deep, practical paragraphs covering:\n"
            f"  1. The core psychological concept\n"
            f"  2. Why most people get this wrong\n"
            f"  3. The Jungian / shadow perspective\n"
            f"  4. Real-world application\n"
            f"  5. An action step the reader must take today\n"
            f"Tone: authoritative, commanding. Speak directly to 'you'. "
            f"Commands and declarations — never suggestions.\n"
            f"NO markdown. Plain paragraphs only."
        )
        return generate_text(prompt).strip()

    def generate_pdf(self, title: str, topic: str) -> str:
        """Generate 10-lesson course PDF. Returns file path."""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.colors import HexColor
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
        from reportlab.lib.enums import TA_CENTER

        # Generate lesson outline
        outline_raw = generate_text(
            f"Create 10 lesson titles for a course called '{title}' about: {topic}\n"
            f"Each lesson should be deep, practical, Jungian in nature.\n"
            f"Return a numbered list 1-10. Lesson title only. Nothing else."
        ).strip()

        lessons = []
        for line in outline_raw.splitlines():
            m = re.match(r"^\d+[\.\)]\s*(.+)", line.strip())
            if m:
                lessons.append(m.group(1).strip())
        if len(lessons) < 5:
            lessons = [f"Core Principle {i + 1}: {topic}" for i in range(10)]
        lessons = lessons[:10]

        slug = re.sub(r"[^a-z0-9]", "-", title.lower()[:30])
        path = os.path.join(ROOT_DIR, ".mp", f"course-{slug}.pdf")

        doc = SimpleDocTemplate(
            path, pagesize=letter,
            rightMargin=inch, leftMargin=inch,
            topMargin=inch, bottomMargin=inch,
        )

        styles = getSampleStyleSheet()
        dark = HexColor("#1a1a2e")
        gold = HexColor("#c4a44d")

        title_s = ParagraphStyle("CT", parent=styles["Title"], fontSize=26,
                                  textColor=dark, alignment=TA_CENTER, spaceAfter=16)
        sub_s = ParagraphStyle("CS", parent=styles["Normal"], fontSize=13,
                                textColor=gold, alignment=TA_CENTER, spaceAfter=6)
        ch_s = ParagraphStyle("CCH", parent=styles["Heading1"], fontSize=18,
                               textColor=dark, spaceBefore=20, spaceAfter=10)
        body_s = ParagraphStyle("CB", parent=styles["Normal"], fontSize=11,
                                 leading=16, spaceAfter=8)

        story = []

        # Cover
        story.append(Spacer(1, inch))
        story.append(Paragraph(title, title_s))
        story.append(Paragraph(f"A Complete Course on {topic}", sub_s))
        story.append(PageBreak())

        # Table of contents
        story.append(Paragraph("Course Outline", ch_s))
        for i, lesson in enumerate(lessons, 1):
            story.append(Paragraph(f"Lesson {i}: {lesson}", body_s))
        story.append(PageBreak())

        # Lesson content
        for i, lesson in enumerate(lessons, 1):
            if get_verbose():
                info(f"Course: writing lesson {i}/{len(lessons)}: {lesson}")
            content = self._generate_lesson(lesson, topic, i)
            story.append(Paragraph(f"Lesson {i}: {lesson}", ch_s))
            story.append(Spacer(1, 0.1 * inch))
            for para in content.split("\n"):
                if para.strip():
                    story.append(Paragraph(para.strip(), body_s))
            story.append(PageBreak())

        doc.build(story)
        if get_verbose():
            info(f"Course: PDF saved → {path}")
        return path

    def list_on_gumroad(self, title: str, topic: str, pdf_path: str) -> str:
        """List course on Gumroad at $19.97. Returns URL."""
        access_token = (
            os.environ.get("GUMROAD_ACCESS_TOKEN", "").strip()
            or get_gumroad_access_token()
        )
        if not access_token:
            if get_verbose():
                warning("Course: GUMROAD_ACCESS_TOKEN not set.")
            return ""

        description = (
            f"A complete 10-lesson course on {topic}. "
            f"Each lesson includes core psychological concepts, practical exercises, "
            f"and actionable steps grounded in Jungian psychology and modern self-development. "
            f"Instant PDF download — read on any device."
        )

        base = "https://api.gumroad.com/v2"
        r = requests.post(f"{base}/products", data={
            "access_token": access_token,
            "name": title[:100],
            "price": 1997,  # $19.97
            "description": description,
        }, timeout=20)

        if not r.ok:
            if get_verbose():
                warning(f"Course: Gumroad create failed {r.status_code}")
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
                    timeout=120,
                )

        requests.put(f"{base}/products/{product_id}", data={
            "access_token": access_token, "published": "true",
        }, timeout=15)

        if get_verbose():
            success(f"Course: Gumroad live → {product_url}")
        return product_url

    def run(self, topic: str) -> str:
        """Generate course title, PDF, and Gumroad listing."""
        title = generate_text(
            f"Create a compelling psychology course title about: {topic}\n"
            f"Use formats like 'The [Topic] Masterclass' or 'Complete [Topic] Blueprint'\n"
            f"Under 60 characters. Return ONLY the title."
        ).strip().strip('"')

        if not title:
            title = f"The {topic} Masterclass"

        if get_verbose():
            info(f"Course: generating '{title}'")

        pdf_path = self.generate_pdf(title, topic)
        return self.list_on_gumroad(title, topic, pdf_path)
