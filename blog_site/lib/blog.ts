import fs from "node:fs";
import path from "node:path";

export type BlogFaq = {
  question: string;
  answer: string;
};

export type BlogPost = {
  title: string;
  slug: string;
  summary: string;
  meta_description: string;
  tags: string[];
  faq: BlogFaq[];
  article_markdown: string;
  generated_utc: string;
  published_at?: string;
};

const contentDir = path.join(process.cwd(), "..", "content", "ai-crypto");

function readPostFile(filePath: string): BlogPost | null {
  try {
    const raw = fs.readFileSync(filePath, "utf-8");
    const parsed = JSON.parse(raw) as BlogPost;
    if (!parsed?.slug || !parsed?.title || !parsed?.article_markdown) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function getAllPosts(): BlogPost[] {
  if (!fs.existsSync(contentDir)) {
    return [];
  }
  const files = fs
    .readdirSync(contentDir)
    .filter((file) => file.endsWith(".json"))
    .sort()
    .reverse();

  return files
    .map((file) => readPostFile(path.join(contentDir, file)))
    .filter((post): post is BlogPost => Boolean(post))
    .sort((a, b) => {
      const aTime = new Date(a.published_at || a.generated_utc).getTime();
      const bTime = new Date(b.published_at || b.generated_utc).getTime();
      return bTime - aTime;
    });
}

export function getPostBySlug(slug: string): BlogPost | null {
  return getAllPosts().find((post) => post.slug === slug) || null;
}

export function markdownToHtml(markdown: string): string {
  const lines = markdown.split(/\r?\n/);
  const html: string[] = [];
  let listBuffer: string[] = [];

  const flushList = () => {
    if (listBuffer.length) {
      html.push("<ul>");
      for (const item of listBuffer) {
        html.push(`<li>${item}</li>`);
      }
      html.push("</ul>");
      listBuffer = [];
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      continue;
    }
    if (line.startsWith("### ")) {
      flushList();
      html.push(`<h3>${line.slice(4)}</h3>`);
      continue;
    }
    if (line.startsWith("## ")) {
      flushList();
      html.push(`<h2>${line.slice(3)}</h2>`);
      continue;
    }
    if (line.startsWith("# ")) {
      flushList();
      html.push(`<h1>${line.slice(2)}</h1>`);
      continue;
    }
    if (line.startsWith("- ")) {
      listBuffer.push(line.slice(2));
      continue;
    }
    flushList();
    html.push(`<p>${line}</p>`);
  }

  flushList();
  return html.join("\n");
}
