import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RAGnarok AI Assistant",
  description: "A highly intelligent, multi-agent AI assistant for IIT Ropar.",
  manifest: "/manifest.json",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: `
          window.deferredPrompt = null;
          window.addEventListener('beforeinstallprompt', (e) => {
            e.preventDefault();
            window.deferredPrompt = e;
          });
        `}} />
      </head>
      <body className="antialiased min-h-screen bg-brand-dark flex">
        {children}
      </body>
    </html>
  );
}
