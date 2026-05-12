export const siteConfig = {
  name: "Signal & Chain",
  shortName: "SignalChain",
  description:
    "Daily AI and crypto analysis built for search intent, practical clarity, and long-term audience growth.",
  defaultSiteUrl:
    process.env.NEXT_PUBLIC_SITE_URL ||
    "https://harshitasharma99999999-creator.github.io/Printer",
  defaultBasePath: process.env.SITE_BASE_PATH || "",
  adsenseClient: process.env.NEXT_PUBLIC_ADSENSE_CLIENT || "",
  adsenseSlotInArticle: process.env.NEXT_PUBLIC_ADSENSE_SLOT_IN_ARTICLE || "",
  adsenseSlotSidebar: process.env.NEXT_PUBLIC_ADSENSE_SLOT_SIDEBAR || "",
  xHandle: "@harshita",
};

export function absoluteUrl(path = ""): string {
  const base = siteConfig.defaultSiteUrl.replace(/\/$/, "");
  const suffix = path.startsWith("/") ? path : `/${path}`;
  return `${base}${path ? suffix : ""}`;
}
