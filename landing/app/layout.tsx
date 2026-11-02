import type { Metadata } from "next";
import { IBM_Plex_Mono, Newsreader, Source_Sans_3 } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "../ui/ThemeProvider";

const display = Newsreader({
  subsets: ["latin"],
  weight: ["500", "600"],
  variable: "--font-display",
});

const sans = Source_Sans_3({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-sans",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "Simply Layout Lab",
  description: "Grocery layout simulation",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning className={`${display.variable} ${sans.variable} ${mono.variable}`}>
      <body>
        <script dangerouslySetInnerHTML={{ __html: `(function(){try{var p=localStorage.getItem('simply-appearance');document.documentElement.dataset.theme=p==='light'||p==='dark'?p:matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'}catch(e){}})()` }} />
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
