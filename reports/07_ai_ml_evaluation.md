# Phase 7 — AI/ML quality evaluation

## Execution status

The repository contains evaluation code and human-review fixtures under `evaluation/`, but this checkout does not contain `data/evaluation_results.json` or `data/ablation_results.json`. No new benchmark numbers were invented or inferred from the historical context document.

| Evaluation | Status | Evidence |
|---|---|---|
| concept precision/recall/F1 | NOT TESTED | no fresh evaluation output |
| fusion pairwise metrics | NOT TESTED | review fixtures exist, but no executed scoring result |
| retrieval P@k/Recall@k/MRR | PARTIAL, freshly computed only on canonical stale corpus | `run_evaluate.py` exit 0; keyword/graph/hybrid ran with 80 concepts and 0 relationships, semantic retriever unavailable because configured Qdrant was unreachable |
| relationship precision/recall/F1 | NOT TESTED | current relationships artifact is empty |
| answer faithfulness/citation accuracy | NOT TESTED | provider unavailable; no result artifact |
| complete workflow rate | NOT TESTED | provider-backed extraction failed for all 40 isolated chunks; no grounded-answer/citation run |

The fresh retrieval run is evidence of executable scoring code, not a valid corpus-quality result. It must not be compared with historical scores until the artifact chain is regenerated and validated. `run_ablation.py` was attempted and exited 1 because its Unicode separator cannot be encoded by the Windows cp1252 console; it produced no scores.

The historical numbers in `CONCEPTSCAPE_PAPER_CONTEXT.md` are labelled as historical ground truth for a prior run and are not reused as current audit measurements.

## Reproducibility requirement

After dependencies and credentials are available, run the repository's documented evaluation scripts (`run_evaluate.py`, `run_review.py`, `run_ablation.py` or the exact supported wrappers), retain versioned fixtures, and write the result files before making any quality claim.

