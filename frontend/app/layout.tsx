import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "smallerDOCS",
  description: "Legal document reconstruction",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-card text-foreground font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
