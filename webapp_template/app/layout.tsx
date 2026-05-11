import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "__APP_NAME__",
  description: "__TAGLINE__",
  manifest: "/manifest.json",
  icons: { apple: "/icon-192.png" },
};

export const viewport = {
  themeColor: "#7c3aed",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
        <script dangerouslySetInnerHTML={{__html: `if('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js');`}} />
      </body>
    </html>
  );
}
