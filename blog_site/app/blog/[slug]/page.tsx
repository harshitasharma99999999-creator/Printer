import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { AdSlot } from "@/components/ad-slot";
import { getAllPosts, getPostBySlug, markdownToHtml } from "@/lib/blog";
import { absoluteUrl, siteConfig } from "@/lib/site";

type PageProps = {
  params: {
    slug: string;
  };
};

export const dynamicParams = false;

export async function generateStaticParams() {
  return getAllPosts().map((post) => ({ slug: post.slug }));
}

export function generateMetadata({ params }: PageProps): Metadata {
  const post = getPostBySlug(params.slug);
  if (!post) {
    return {};
  }
  const url = absoluteUrl(`/blog/${post.slug}`);
  return {
    title: post.title,
    description: post.meta_description || post.summary,
    alternates: {
      canonical: url,
    },
    openGraph: {
      title: post.title,
      description: post.meta_description || post.summary,
      type: "article",
      url,
      publishedTime: post.published_at || post.generated_utc,
    },
    twitter: {
      card: "summary_large_image",
      title: post.title,
      description: post.meta_description || post.summary,
    },
    keywords: post.tags,
  };
}

export default function BlogPostPage({ params }: PageProps) {
  const post = getPostBySlug(params.slug);
  if (!post) {
    notFound();
  }

  const html = markdownToHtml(post.article_markdown);
  const articleUrl = absoluteUrl(`/blog/${post.slug}`);
  const articleSchema = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.meta_description || post.summary,
    datePublished: post.published_at || post.generated_utc,
    dateModified: post.generated_utc,
    author: {
      "@type": "Organization",
      name: siteConfig.name,
    },
    publisher: {
      "@type": "Organization",
      name: siteConfig.name,
    },
    mainEntityOfPage: articleUrl,
    keywords: post.tags.join(", "),
  };

  const faqSchema =
    post.faq?.length
      ? {
          "@context": "https://schema.org",
          "@type": "FAQPage",
          mainEntity: post.faq.map((item) => ({
            "@type": "Question",
            name: item.question,
            acceptedAnswer: {
              "@type": "Answer",
              text: item.answer,
            },
          })),
        }
      : null;

  return (
    <>
      <header className="topbar">
        <div className="container topbar-inner">
          <Link href="/" className="brand">
            <span className="brand-mark">AI x Crypto</span>
            <span className="brand-name">{siteConfig.name}</span>
          </Link>
          <nav className="nav-links">
            <Link href="/">Home</Link>
            <a href="#faq">FAQ</a>
          </nav>
        </div>
      </header>

      <main className="container article-grid">
        <article className="article-shell">
          <div className="article-kicker">AI and crypto analysis</div>
          <h1 className="article-title" style={{ fontFamily: "var(--font-heading), serif" }}>
            {post.title}
          </h1>
          <p className="article-summary">{post.summary}</p>

          <div className="tag-row" style={{ marginTop: "1.25rem" }}>
            {post.tags.map((tag) => (
              <span className="tag" key={tag}>
                #{tag}
              </span>
            ))}
          </div>

          <div
            className="article-body"
            dangerouslySetInnerHTML={{ __html: html }}
          />

          {post.faq?.length ? (
            <section id="faq" style={{ marginTop: "2rem" }}>
              <h2 style={{ fontFamily: "var(--font-heading), serif" }}>FAQ</h2>
              {post.faq.map((item) => (
                <div className="faq-item" key={item.question}>
                  <h3 style={{ fontFamily: "var(--font-heading), serif" }}>{item.question}</h3>
                  <p>{item.answer}</p>
                </div>
              ))}
            </section>
          ) : null}
        </article>

        <aside className="sidebar-stack">
          <div className="sidebar-card">
            <h3 style={{ fontFamily: "var(--font-heading), serif" }}>Why this ranks better</h3>
            <ul>
              <li>Dedicated title, summary, and meta description.</li>
              <li>Static article URL with clean slug.</li>
              <li>Article schema plus FAQ schema.</li>
              <li>Sitemap and robots file included for crawl discovery.</li>
            </ul>
          </div>
          <AdSlot slot={siteConfig.adsenseSlotSidebar} label="Ad placement" />
        </aside>
      </main>

      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleSchema) }}
      />
      {faqSchema ? (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
        />
      ) : null}
    </>
  );
}
