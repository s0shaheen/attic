import type { Metadata } from "next";
import { Crimson_Pro, DM_Mono, DM_Sans } from "next/font/google";
import { DevBanner } from "@/components/dev-banner";
import { Providers } from "@/components/providers";
import "./globals.css";

const dmSans = DM_Sans({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-sans",
  display: "swap",
});

const crimsonPro = Crimson_Pro({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-display",
  display: "swap",
});

const dmMono = DM_Mono({
  subsets: ["latin"],
  weight: ["400"],
  variable: "--font-mono",
  display: "swap",
});

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
    <html lang="en" className={`${dmSans.variable} ${crimsonPro.variable} ${dmMono.variable}`}>
      <body className="min-h-screen antialiased">
        <Providers>
          <DevBanner />
          {children}
        </Providers>
      </body>
    </html>
  );
}
