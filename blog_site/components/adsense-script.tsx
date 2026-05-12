"use client";

import Script from "next/script";
import { siteConfig } from "@/lib/site";

export function AdSenseScript() {
  if (!siteConfig.adsenseClient) {
    return null;
  }

  return (
    <Script
      id="adsense-script"
      async
      strategy="afterInteractive"
      crossOrigin="anonymous"
      src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${siteConfig.adsenseClient}`}
    />
  );
}
