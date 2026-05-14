import type { Metadata } from "next";
import { Merriweather, Space_Grotesk } from "next/font/google";
import { AdSenseScript } from "@/components/adsense-script";
import { absoluteUrl, siteConfig } from "@/lib/site";
import "./globals.css";

const headingFont = Merriweather({
  subsets: ["latin"],
  variable: "--font-heading",
  weight: ["400", "700", "900"],
});

const bodyFont = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-body",
  weight: ["400", "500", "700"],
});

export const metadata: Metadata = {
  metadataBase: new URL(siteConfig.defaultSiteUrl),
  title: {
    default: `${siteConfig.name} | AI and Crypto Blog`,
    template: `%s | ${siteConfig.name}`,
  },
  description: siteConfig.description,
  alternates: {
    canonical: absoluteUrl("/"),
  },
  openGraph: {
    title: `${siteConfig.name} | AI and Crypto Blog`,
    description: siteConfig.description,
    type: "website",
    url: absoluteUrl("/"),
    siteName: siteConfig.name,
  },
  twitter: {
    card: "summary_large_image",
    title: `${siteConfig.name} | AI and Crypto Blog`,
    description: siteConfig.description,
  },
  other: siteConfig.adsenseClient
    ? {
        "google-adsense-account": siteConfig.adsenseClient,
      }
    : undefined,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body
        className={`${headingFont.variable} ${bodyFont.variable} page-shell`}
        style={{
          fontFamily: "var(--font-body), sans-serif",
        }}
      >
        <AdSenseScript />
        {children}
      </body>
    </html>
  );
}
