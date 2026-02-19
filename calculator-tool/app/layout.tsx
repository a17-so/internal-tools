import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Deal Calculator",
  description: "CPM deal calculator for creator partnerships",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="antialiased">{children}</body>
    </html>
  );
}
