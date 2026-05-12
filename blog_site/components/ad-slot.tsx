"use client";

import { useEffect } from "react";
import { siteConfig } from "@/lib/site";

declare global {
  interface Window {
    adsbygoogle?: unknown[];
  }
}

type AdSlotProps = {
  slot?: string;
  label?: string;
};

export function AdSlot({ slot, label = "Advertisement" }: AdSlotProps) {
  const client = siteConfig.adsenseClient;

  useEffect(() => {
    if (!client || !slot) {
      return;
    }
    try {
      window.adsbygoogle = window.adsbygoogle || [];
      window.adsbygoogle.push({});
    } catch {
      // Best-effort only. Empty placeholders are acceptable before AdSense approval.
    }
  }, [client, slot]);

  if (!client || !slot) {
    return (
      <div className="ad-shell">
        <strong>{label}</strong>
        <p className="ad-note">
          AdSense placeholder. Add your `NEXT_PUBLIC_ADSENSE_CLIENT` and slot IDs to show real ads.
        </p>
      </div>
    );
  }

  return (
    <div className="ad-shell">
      <ins
        className="adsbygoogle"
        style={{ display: "block" }}
        data-ad-client={client}
        data-ad-slot={slot}
        data-ad-format="auto"
        data-full-width-responsive="true"
      />
    </div>
  );
}
