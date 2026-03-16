import type { Metadata } from "next";
import { DevBanner } from "@/components/dev-banner";
import { Providers } from "@/components/providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Attic",
  description: "Your entire TikTok history, finally organized and searchable.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen antialiased">
        <Providers>
          <DevBanner />
          {children}
        </Providers>
      </body>
    </html>
  );
}
