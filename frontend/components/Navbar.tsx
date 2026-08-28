"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";
import { Network } from "lucide-react";

export function Navbar({ rightSlot }: { rightSlot?: React.ReactNode }) {
  const pathname = usePathname();

  const navs = [
    { name: "Home", path: "/" },
    { name: "Graph", path: "/graph" },
    { name: "Ask", path: "/chat" },
    { name: "Documents", path: "/upload" },
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
    </div>
  );
}
