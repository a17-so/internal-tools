import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const instrumentSans = localFont({
  variable: "--font-instrument-sans",
  src: [
    { path: "./fonts/InstrumentSans-Medium.ttf", weight: "500", style: "normal" },
    { path: "./fonts/InstrumentSans-SemiBold.ttf", weight: "600", style: "normal" },
    { path: "./fonts/InstrumentSans-Bold.ttf", weight: "700", style: "normal" },
  ],
});

const sohne = localFont({
  variable: "--font-sohne",
  src: [
    { path: "./fonts/Sohne-Semibold.otf", weight: "600", style: "normal" },
    { path: "./fonts/Sohne-Bold.otf", weight: "700", style: "normal" },
    { path: "./fonts/Sohne-Heavy.otf", weight: "800", style: "normal" },
  ],
});

export const metadata: Metadata = {
  title: "Regen Creator Web",
  description: "Browser recreation of the creator-only iOS flow",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className={`${instrumentSans.variable} ${sohne.variable}`}>{children}</body>
    </html>
  );
}
