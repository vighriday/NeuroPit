import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "NeuroPit Cognitive Twin OS",
  description:
    "Real time Cognitive Twin Operating System for motorsport. Telemetry is infrastructure. Cognition is the product.",
  icons: {
    icon: "/neuropit-logo.png",
    shortcut: "/neuropit-logo.png",
    apple: "/neuropit-logo.png",
  },
  openGraph: {
    title: "NeuroPit Cognitive Twin OS",
    description:
      "Real time Cognitive Twin Operating System for motorsport. Telemetry is infrastructure. Cognition is the product.",
    images: ["/neuropit-logo.png"],
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>{children}</body>
    </html>
  );
}
