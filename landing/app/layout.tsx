import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = { title: "Simply Layout Lab", description: "Grocery layout simulation" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
