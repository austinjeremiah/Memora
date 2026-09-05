import type { Metadata } from "next";

import "@/styles/framer.css";
import "@/styles/breakpoints.css";
import "@/styles/fonts.css";
import "@/styles/app.css";

const FAVICON =
  "https://framerusercontent.com/images/1VtXtUrlVK0Y1WHlW4GIfnhxFho.png";
const OG_IMAGE =
  "https://framerusercontent.com/assets/LaGEDiVbTeEg75rIXlNKdeL8x4.png";

const DESCRIPTION =
  "MEMORA is a persistent clinical memory and safety system built on Sibyl Memory and Base. Every AI-proposed claim is checked against real evidence before it reaches a clinician, and Sentinel watches memory for drift with zero LLM in the detection path.";

export const metadata: Metadata = {
  title: "MEMORA - Persistent Clinical Memory & Safety Gate",
  description: DESCRIPTION,
  metadataBase: new URL("https://cosmoq.framer.website/"),
  alternates: { canonical: "/" },
  robots: { "max-image-preview": "large" },
  icons: { icon: FAVICON, apple: FAVICON },
  openGraph: {
    type: "website",
    url: "https://cosmoq.framer.website/",
    title: "MEMORA - Persistent Clinical Memory & Safety Gate",
    description: DESCRIPTION,
    images: [OG_IMAGE],
  },
  twitter: {
    card: "summary_large_image",
    title: "MEMORA - Persistent Clinical Memory & Safety Gate",
    description: DESCRIPTION,
    images: [OG_IMAGE],
  },
};

export const viewport = { width: "device-width" };

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
