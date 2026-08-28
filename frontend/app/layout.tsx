import "./globals.css";
import "reactflow/dist/style.css";

export const metadata = {
  title: "ConceptScape",
  description: "Evidence-grounded concept knowledge graph",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
