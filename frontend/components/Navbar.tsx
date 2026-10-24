"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Network } from "lucide-react";
import { clearSession, getToken } from "@/lib/auth";

export function Navbar({ rightSlot }: { rightSlot?: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [signedIn, setSignedIn] = useState(false);

  useEffect(() => setSignedIn(Boolean(getToken())), []);

  const navs = [
    { name: "Home", path: "/" },
    { name: "Graph", path: "/graph" },
    { name: "Ask", path: "/chat" },
    { name: "Documents", path: "/upload" },
    { name: "Workspace", path: "/workspace" },
    { name: "Learn", path: "/learn" },
    { name: "Progress", path: "/progress" },
    { name: "Quality", path: "/quality" },
    { name: "Admin", path: "/admin" },
  ];

  return (
    <div className="topbar">
      <Link href="/" className="title-area">
        <Network size={18} className="title-icon" />
        <span className="title">ConceptScape</span>
      </Link>

      <nav className="nav-inline">
        {navs.map((n) => {
          const isActive = pathname === n.path;
          return (
            <Link key={n.path} href={n.path} className={`nav-link ${isActive ? "active" : ""}`}>
              {n.name}
              {isActive && (
                <motion.div
                  layoutId="navbar-indicator"
                  className="nav-indicator"
                  transition={{ type: "spring", stiffness: 300, damping: 30 }}
                />
              )}
            </Link>
          );
        })}
      </nav>

      {rightSlot && <div className="nav-right">{rightSlot}</div>}
      <div className="nav-right">
        {signedIn ? (
          <button className="btn-ghost" onClick={() => { clearSession(); setSignedIn(false); router.push("/login"); }}>Sign out</button>
        ) : (
          <button className="btn-ghost" onClick={() => router.push("/login")}>Sign in</button>
        )}
      </div>
    </div>
  );
}
