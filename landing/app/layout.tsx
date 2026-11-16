import type { Metadata } from "next";
import { IBM_Plex_Mono, Inter } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "../ui/ThemeProvider";

const sans = Inter({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-sans",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Simply",
  description: "Spot impulse buys in simulated shopping trips.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning className={`${sans.variable} ${mono.variable}`}>
      <body>
        <script dangerouslySetInnerHTML={{ __html: `(function(){try{var p=localStorage.getItem('simply-appearance');document.documentElement.dataset.theme=p==='light'||p==='dark'?p:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}catch(e){}})()` }} />
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
