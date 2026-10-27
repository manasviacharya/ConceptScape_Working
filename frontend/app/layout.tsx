import "./globals.css";
import "reactflow/dist/style.css";
import { LenisProvider } from "@/components/LenisProvider";
import { PageTransition } from "@/components/PageTransition";

export const metadata = {
  title: "ConceptScape",
  description: "Evidence-grounded concept knowledge graph",
};

export const viewport = {
  themeColor: "#0d0d10",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <LenisProvider>
          <PageTransition>
            {children}
          </PageTransition>
        </LenisProvider>
      </body>
    </html>
  );
}
