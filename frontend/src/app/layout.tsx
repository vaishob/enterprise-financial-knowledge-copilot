import type { Metadata } from "next";
import { Shell } from "@/components/shell";
import "./globals.css";
export const metadata: Metadata = {title: "Knowledge Copilot | Enterprise Financial Knowledge", description: "Role-aware synthetic financial-policy knowledge and evaluation workspace.", robots: {index: false, follow: false}};
export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="en"><body><Shell>{children}</Shell></body></html>;
}
