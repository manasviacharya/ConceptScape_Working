"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import {
  Network,
  Upload,
  Brain,
  MessageSquare,
  ArrowRight,
  Sparkles,
  FileText,
  GitBranch,
  Search,
  Zap,
  Shield,
} from "lucide-react";
import { Navbar } from "@/components/Navbar";
import { getHealth, type HealthStatus } from "@/lib/api";

const FEATURES = [
  {
    icon: Upload,
    title: "Multi-Format Ingestion",
    desc: "Drop PDFs, PowerPoints, or images. PaddleOCR handles scanned pages automatically.",
    color: "#22c55e",
  },
  {
    icon: Brain,
    title: "AI Concept Extraction",
    desc: "Gemini & Groq extract concepts, definitions, and relationships — every claim verified against source text.",
    color: "#7c5cfc",
  },
  {
    icon: GitBranch,
    title: "Knowledge Graph",
    desc: "Concepts become nodes, relationships become edges. Explore how ideas connect across your documents.",
    color: "#3d8dae",
  },
  {
    icon: MessageSquare,
    title: "Grounded Q&A",
    desc: "Ask questions and get cited answers. If the material doesn't cover it, ConceptScape says so.",
    color: "#f59e0b",
  },
  {
    icon: Shield,
    title: "Evidence-First",
    desc: "No hallucinations. Every concept, edge, and answer traces back to a specific page in your documents.",
    color: "#e07a5f",
  },
  {
    icon: Zap,
    title: "7-Stage Pipeline",
    desc: "Ingest, Clean, Extract, Normalize, Relate, Graph, Index. Cached and resumable.",
    color: "#8a63d2",
  },
];

const STEPS = [
  { num: "01", title: "Upload Documents", desc: "PDF, PPTX, JPG, PNG — drag and drop.", icon: FileText },
  { num: "02", title: "Run Pipeline", desc: "AI extracts concepts and builds the graph.", icon: Sparkles },
  { num: "03", title: "Explore & Ask", desc: "Navigate the graph or ask questions with cited answers.", icon: Search },
];

const PIPELINE = ["Ingest", "Clean", "Extract", "Normalize", "Relate", "Graph", "Index"];

export default function LandingPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [backendUp, setBackendUp] = useState<boolean | null>(null);

  useEffect(() => {
    getHealth()
      .then((h) => { setHealth(h); setBackendUp(true); })
      .catch(() => setBackendUp(false));
  }, []);

  const artifactCount = health
    ? Object.values(health.artifacts).filter(Boolean).length
    : 0;

  return (
    <div className="landing">
      <Navbar />

      {/* Hero */}
      <section className="hero">
        <div className="hero-glow" />
        <div className="hero-content">
          <motion.div
            className="hero-badge"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Sparkles size={14} />
            AI-Powered Learning Workspace
          </motion.div>

          <motion.h1
            className="hero-title"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            Turn Documents into
            <span className="hero-gradient"> Knowledge Graphs</span>
          </motion.h1>

          <motion.p
            className="hero-sub"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
          >
            Upload your study material. ConceptScape extracts concepts,
            maps relationships, and lets you explore and ask questions —
            every answer grounded in evidence from your documents.
          </motion.p>

          <motion.div
            className="hero-actions"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.3 }}
          >
            <Link href="/upload" className="hero-cta">
              Get Started
              <ArrowRight size={18} />
            </Link>
            <Link href="/graph" className="hero-cta-secondary">
              <Network size={18} />
              Explore Graph
            </Link>
          </motion.div>

          <motion.div
            className="hero-status"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.4 }}
          >
            <span className={`status-dot ${backendUp === true ? "up" : backendUp === false ? "down" : ""}`} />
            {backendUp === null
              ? "Checking backend…"
              : backendUp
                ? `Backend online · ${artifactCount}/4 artifacts ready`
                : "Backend offline — start with: uvicorn api.service:app --port 8000"}
          </motion.div>
        </div>

        <motion.div
          className="hero-visual"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.3, duration: 0.6 }}
        >
          <GraphPreview />
        </motion.div>
      </section>

      {/* How it works */}
      <section className="section">
        <div className="section-header">
          <span className="section-label">How It Works</span>
          <h2 className="section-title">Three Steps to Understanding</h2>
        </div>
        <div className="steps-grid">
          {STEPS.map((step) => (
            <div key={step.num} className="step-card">
              <span className="step-num">{step.num}</span>
              <div className="step-icon-wrap">
                <step.icon size={24} />
              </div>
              <h3>{step.title}</h3>
              <p>{step.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Features */}
      <section className="section">
        <div className="section-header">
          <span className="section-label">Features</span>
          <h2 className="section-title">Built for Deep Understanding</h2>
        </div>
        <div className="features-grid">
          {FEATURES.map((f) => (
            <div key={f.title} className="feature-card">
              <div className="feature-icon" style={{ background: `${f.color}15`, color: f.color }}>
                <f.icon size={22} />
              </div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pipeline */}
      <section className="section">
        <div className="section-header">
          <span className="section-label">Pipeline</span>
          <h2 className="section-title">Seven Stages, Fully Automated</h2>
        </div>
        <div className="pipeline-bar">
          {PIPELINE.map((s, i) => (
            <div key={s} className="pipeline-stage">
              <span className="pipeline-num">{i + 1}</span>
              <span>{s}</span>
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="section cta-section">
        <div className="cta-block">
          <div className="cta-glow" />
          <h2>Ready to Build Your Knowledge Graph?</h2>
          <p>Upload your first document and watch ConceptScape map out the concepts.</p>
          <div style={{ display: "flex", gap: 16, justifyContent: "center" }}>
            <Link href="/upload" className="hero-cta">
              Upload Documents <ArrowRight size={18} />
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <Network size={16} style={{ color: "var(--accent)" }} />
            <span>ConceptScape</span>
          </div>
          <span className="footer-text">Evidence-grounded concept knowledge graph</span>
        </div>
      </footer>
    </div>
  );
}

function GraphPreview() {
  const nodes = [
    { id: "ml", label: "Machine Learning", x: 200, y: 40, main: true },
    { id: "gd", label: "Gradient Descent", x: 120, y: 130, main: false },
    { id: "lr", label: "Learning Rate", x: 310, y: 110, main: false },
    { id: "nn", label: "Neural Network", x: 50, y: 60, main: false },
    { id: "opt", label: "Optimization", x: 80, y: 210, main: false },
    { id: "lf", label: "Loss Function", x: 300, y: 200, main: false },
    { id: "bp", label: "Backpropagation", x: 220, y: 260, main: false },
  ];

  const edges = [
    { from: "ml", to: "gd" }, { from: "ml", to: "lr" }, { from: "ml", to: "nn" },
    { from: "gd", to: "opt" }, { from: "gd", to: "lf" }, { from: "nn", to: "bp" },
    { from: "bp", to: "gd" }, { from: "lr", to: "lf" },
  ];

  return (
    <svg viewBox="0 0 420 310" className="graph-preview">
      <defs>
        <radialGradient id="node-glow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="var(--accent)" stopOpacity="0.3" />
          <stop offset="100%" stopColor="var(--accent)" stopOpacity="0" />
        </radialGradient>
      </defs>
      {edges.map((e, i) => {
        const from = nodes.find((n) => n.id === e.from)!;
        const to = nodes.find((n) => n.id === e.to)!;
        return (
          <line
            key={i}
            x1={from.x + 50} y1={from.y + 16}
            x2={to.x + 50} y2={to.y + 16}
            stroke="var(--border-med)"
            strokeWidth="1.5"
            opacity="0.6"
          />
        );
      })}
      {nodes.map((n) => (
        <g key={n.id}>
          {n.main && <circle cx={n.x + 50} cy={n.y + 16} r="40" fill="url(#node-glow)" />}
          <rect
            x={n.x} y={n.y}
            width="100" height="32" rx="8"
            fill={n.main ? "rgba(124,92,252,0.15)" : "var(--surface-2)"}
            stroke={n.main ? "var(--accent)" : "var(--border-med)"}
            strokeWidth={n.main ? "1.5" : "1"}
          />
          <text
            x={n.x + 50} y={n.y + 20}
            textAnchor="middle"
            fill="var(--text)"
            fontSize="10"
            fontWeight={n.main ? "600" : "500"}
            fontFamily="var(--font-inter), sans-serif"
          >
            {n.label}
          </text>
        </g>
      ))}
    </svg>
  );
}
