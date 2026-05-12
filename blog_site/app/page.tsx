import Link from "next/link";
import { AdSlot } from "@/components/ad-slot";
import { getAllPosts } from "@/lib/blog";
import { absoluteUrl, siteConfig } from "@/lib/site";

export default function HomePage() {
  const posts = getAllPosts();
  const featured = posts[0];
  const latest = posts.slice(1, 7);

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
            <a href="#latest">Latest</a>
            <a href={absoluteUrl("/sitemap.xml")}>Sitemap</a>
          </nav>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="container hero-grid">
            <div>
              <span className="eyebrow">Built for search intent</span>
              <h1 style={{ fontFamily: "var(--font-heading), serif" }}>
                Daily AI and crypto articles designed to rank and compound.
              </h1>
              <p>
                This site publishes practical, search-focused articles around AI agents, blockchain,
                onchain analytics, crypto strategy, and the real business impact of new tooling.
                Each post is written with strong metadata, FAQ structure, and clean internal publishing.
              </p>
            </div>
            <aside className="hero-card">
              <h3 style={{ fontFamily: "var(--font-heading), serif" }}>SEO stack</h3>
              <div className="metric">
                <span className="metric-label">Public article pages</span>
                <span className="metric-value">{posts.length}</span>
              </div>
              <div className="metric">
                <span className="metric-label">Structured for Google</span>
                <span className="metric-value">Metadata + FAQ + Schema</span>
              </div>
              <div className="metric">
                <span className="metric-label">Monetization ready</span>
                <span className="metric-value">AdSense slots added</span>
              </div>
            </aside>
          </div>
        </section>

        {featured && (
          <section className="section">
            <div className="container">
              <div className="section-head">
                <div>
                  <h2 style={{ fontFamily: "var(--font-heading), serif" }}>Featured article</h2>
                  <p>The freshest long-form piece from the automated publishing pipeline.</p>
                </div>
              </div>

              <article className="post-card">
                <div className="post-meta">
                  {new Date(featured.published_at || featured.generated_utc).toLocaleDateString()}
                </div>
                <h3 style={{ fontFamily: "var(--font-heading), serif", fontSize: "2rem" }}>
                  <Link href={`/blog/${featured.slug}`}>{featured.title}</Link>
                </h3>
                <p>{featured.summary}</p>
                <div className="tag-row">
                  {featured.tags.map((tag) => (
                    <span className="tag" key={tag}>
                      #{tag}
                    </span>
                  ))}
                </div>
                <Link href={`/blog/${featured.slug}`} className="read-link">
                  Read the full article
                </Link>
              </article>
            </div>
          </section>
        )}

        <section className="section" id="latest">
          <div className="container">
            <div className="section-head">
              <div>
                <h2 style={{ fontFamily: "var(--font-heading), serif" }}>Latest articles</h2>
                <p>Search-friendly posts around AI tools, crypto research, market structure, and Web3 execution.</p>
              </div>
            </div>

            <div className="post-grid">
              {latest.map((post) => (
                <article key={post.slug} className="post-card">
                  <div className="post-meta">
                    {new Date(post.published_at || post.generated_utc).toLocaleDateString()}
                  </div>
                  <h3 style={{ fontFamily: "var(--font-heading), serif" }}>
                    <Link href={`/blog/${post.slug}`}>{post.title}</Link>
                  </h3>
                  <p>{post.summary}</p>
                  <div className="tag-row">
                    {post.tags.map((tag) => (
                      <span className="tag" key={tag}>
                        #{tag}
                      </span>
                    ))}
                  </div>
                  <Link href={`/blog/${post.slug}`} className="read-link">
                    Read more
                  </Link>
                </article>
              ))}
            </div>
          </div>
        </section>

        <section className="section">
          <div className="container">
            <AdSlot slot={siteConfig.adsenseSlotInArticle} label="Sponsored" />
          </div>
        </section>
      </main>

      <footer className="footer">
        <div className="container">
          {siteConfig.name} publishes daily AI + crypto articles with structured SEO metadata, FAQs,
          and monetization-ready AdSense placement.
        </div>
      </footer>
    </>
  );
}
