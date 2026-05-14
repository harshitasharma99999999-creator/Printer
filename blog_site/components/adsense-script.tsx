"use client";

import Script from "next/script";
import { siteConfig } from "@/lib/site";

export function AdSenseScript() {
  if (!siteConfig.adsenseClient) {
    return null;
  }

  return (
    <>
      <Script
        id="adsense-script"
        async
        strategy="afterInteractive"
        crossOrigin="anonymous"
        src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${siteConfig.adsenseClient}`}
      />
      <Script
        id="adsense-auto-ads"
        strategy="afterInteractive"
        dangerouslySetInnerHTML={{
          __html: `
            window.adsbygoogle = window.adsbygoogle || [];
            window.adsbygoogle.push({
              google_ad_client: "${siteConfig.adsenseClient}",
              enable_page_level_ads: true
            });
          `,
        }}
      />
    </>
  );
}
