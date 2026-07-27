import type { Metadata } from "next";
import "./globals.css";
import { Roboto_Slab } from "next/font/google";
import { cn } from "@/lib/utils";

const robotoSlab = Roboto_Slab({subsets:['latin'],variable:'--font-serif'});

export const metadata: Metadata = {
  title: "RepoSage | Understand any repository",
  description: "Retrieval-grounded chat for public GitHub repositories.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" className={cn("font-serif", robotoSlab.variable)}><body>{children}</body></html>;
}
