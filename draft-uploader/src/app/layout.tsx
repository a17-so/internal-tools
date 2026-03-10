import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Daemon Uploader",
  description: "Connect TikTok and upload videos to draft from desktop.",
};

import { Toaster } from "@/components/ui/sonner";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
