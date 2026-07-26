import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RepoSage | Understand any repository",
  description: "Retrieval-grounded chat for public GitHub repositories.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
