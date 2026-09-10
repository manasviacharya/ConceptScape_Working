"""
Manual-annotation evaluations: fusion decisions, relationship precision,
concept precision.

    python run_review.py fusion       --prepare    # write the review sheet
    python run_review.py relationships --prepare
    python run_review.py concepts      --prepare

Then edit evaluation/reviews/<name>.json, setting "verdict" on each item to
"correct", "incorrect" or "unsure". Re-running --prepare keeps existing verdicts.

    python run_review.py fusion                    # score what has been judged

The judgement has to be yours: an evaluation where the system grades its own
output is not an evaluation.
"""
import argparse
import json
import os

from config import settings
from evaluation.review import load_sheet, print_report, sample, score, write_sheet


def _load(name):
    with open(os.path.join(settings.data_dir, name), encoding="utf-8") as f:
        return json.load(f)


# ── A3: fusion decisions ────────────────────────────────────────────────
def prepare_fusion():
    data = _load("normalized_concepts.json")
    decisions = data.get("fusion_decisions", [])
    if not decisions:
        print("No fusion_decisions found — re-run run_normalization.py to record them.")
        return

    items = [{
        "id": f"fus{i:03d}",
        "decision": d.get("decision", "merged"),
        "concept_a": d["a"],
        "concept_b": d["b"],
        "similarity": d["similarity"],
        "system_reason": d["reason"],
        "question": ("Are these the same concept, and should they have been merged?"
                     if d.get("decision") == "merged"
                     else "Are these genuinely different concepts, i.e. was holding them apart right?"),
    } for i, d in enumerate(decisions)]

    path = write_sheet("fusion", items, [
        "Set verdict='correct' if the system's decision was right.",
        "For a 'merged' item: correct means they really are one concept.",
        "For a 'held_apart' item: correct means they really are different concepts.",
        "Refusals matter as much as merges — a system that never refuses is not conservative.",
    ])
    print(f"{len(items)} fusion decisions written to {path}")


# ── A4: relationship precision ──────────────────────────────────────────
def prepare_relationships(n=40):
    rels = _load("relationships.json")["relationships"]
    chosen = sample(rels, n)
    items = [{
        "id": f"rel{i:03d}",
        "relationship": f"{r['source_name']} —{r['type']}→ {r['target_name']}",
        "type": r["type"],
        "evidence": (r.get("evidence") or [{}])[0].get("text", ""),
        "source": (r.get("evidence") or [{}])[0].get("filename", ""),
        "scope": (r.get("evidence") or [{}])[0].get("scope", ""),
        "question": "Does the evidence actually support this relationship, in this direction?",
    } for i, r in enumerate(chosen)]

    path = write_sheet("relationships", items, [
        "Set verdict='correct' if the evidence supports the relationship AS STATED.",
        "Direction matters: 'A requires B' is wrong if the text says B requires A.",
        "Mark incorrect if the evidence merely mentions both concepts without relating them.",
        "Mark incorrect if the relationship type is wrong even though a relationship exists.",
    ])
    print(f"{len(items)} of {len(rels)} relationships sampled to {path}")


# ── A5: concept precision ───────────────────────────────────────────────
def prepare_concepts(n=50):
    concepts = _load("normalized_concepts.json")["concepts"]
    chosen = sample(concepts, n)
    items = [{
        "id": f"con{i:03d}",
        "concept": c["canonical_name"],
        "definition": c.get("definition", ""),
        "evidence": (c.get("evidence") or [""])[0],
        "sources": c.get("filenames", [])[:2],
        "occurrences": c.get("occurrence_count", 0),
        "question": "Is this a real teachable concept, and is the definition supported by the evidence?",
    } for i, c in enumerate(chosen)]

    path = write_sheet("concepts", items, [
        "Set verdict='correct' only if BOTH hold:",
        "  1. it is a genuine teachable concept, not a slide title, table label,",
        "     worked example or bare equation;",
        "  2. the definition is supported by the evidence span, not by outside knowledge.",
        "Mark incorrect if it is trivial — e.g. a concept whose definition is a",
        "numeric result like 'error = 2.76 - 6 = -3.24'.",
    ])
    print(f"{len(items)} of {len(concepts)} concepts sampled to {path}")


TASKS = {
    "fusion": (prepare_fusion, "Fusion decision accuracy", "decision"),
    "relationships": (prepare_relationships, "Relationship extraction precision", "type"),
    "concepts": (prepare_concepts, "Concept extraction precision", ""),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task", choices=sorted(TASKS))
    ap.add_argument("--prepare", action="store_true")
    ap.add_argument("-n", type=int, default=None)
    args = ap.parse_args()

    prepare, title, group_by = TASKS[args.task]

    if args.prepare:
        prepare(args.n) if args.n and args.task != "fusion" else prepare()
        print("\nEdit the file, set a verdict on each item, then re-run without --prepare.")
        return

    items = load_sheet(args.task)
    print_report(title, score(items, group_by), group_by)
    print()


if __name__ == "__main__":
    main()
