import type { MetadataRoute } from "next";
import { getAllPosts } from "@/lib/blog";
import { absoluteUrl } from "@/lib/site";

export default function sitemap(): MetadataRoute.Sitemap {
  const posts = getAllPosts();
  const entries: MetadataRoute.Sitemap = [
    {
      url: absoluteUrl("/"),
      lastModified: new Date(),
      changeFrequency: "daily" as const,
      priority: 1,
    },
  ];

  return entries.concat(
    posts.map((post): MetadataRoute.Sitemap[number] => ({
      url: absoluteUrl(`/blog/${post.slug}`),
      lastModified: new Date(post.published_at || post.generated_utc),
      changeFrequency: "weekly" as const,
      priority: 0.8,
    }))
  );
}
