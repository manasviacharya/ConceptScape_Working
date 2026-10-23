# ConceptScape — Ground Truth Context for Research Paper Assessment

**Purpose of this document.** It states what the ConceptScape system actually
does and what its evaluation actually produced, so that a reviewer can assess
the accompanying research paper against verified fact rather than against the
paper's own claims. Every number here was read directly from the project's
output files. Where the paper disagrees with this document, **this document is
correct and the paper is wrong**.

Date of verification: 2026-09-09. Corpus and code unchanged since.

---

## 1. What the system is

ConceptScape converts educational documents (PDF, PPTX, images, YouTube) into
an evidence-grounded concept knowledge graph, and answers questions against it
with citations back to specific source locations.

Its defining constraint: **an LLM may not assert anything it cannot quote.**
Every concept and relationship must carry a verbatim span from the source. Each
span is verified programmatically — NFKC normalisation, whitespace collapse,
casefold, substring match against first the cleaned chunk and then the raw page
text. Anything whose quote cannot be located is discarded. Spans under 10
characters are rejected.

Pipeline: ingestion → preprocessing → extraction → normalisation → fusion →
relationship extraction → graph construction → indexing → retrieval → RAG.
Each stage reads and writes JSON and caches on a content hash. Failures are
deliberately NOT cached, so a quota-interrupted run resumes rather than
recording failures as empty results.

---

## 2. Implementation facts

| Property | Value |
|---|---|
| Python | ~6,500 lines, 64 modules (excl. tests, frontend) |
| Tests | 76 automated checks across 3 suites, model calls stubbed |
| Frontend | Next.js + React Flow |
| API | FastAPI |
| Embeddings | BGE-M3, 1024-dim |
| Graph store | Neo4j, with in-memory fallback |
| Vector store | Qdrant, with embedded local fallback |
| LLM primary | `gemini-3.6-flash` |
| LLM fallback | Groq `openai/gpt-oss-120b` |

**Model usage in the reported run: 124 of 131 mentions (95%) came from Groq**,
not Gemini. Gemini's free tier is 20 requests/day and was exhausted almost
immediately; a class-level circuit breaker disables it for the rest of a run.

### Key algorithms

- **Normalisation (lexical):** match_key via NFKC, casefold, plural fold,
  parenthetical strip, corpus-learned abbreviations.
- **Fusion (semantic):** BGE-M3 cosine ≥ 0.80 as a *pre-filter only*, then
  **deterministic rule-based guards** — initialism expansion derived from the
  compared pair, substring containment, and a discriminator-word list
  (mini/batch/stochastic/global/local/…). Then union-find for transitive
  merges. Provenance is unioned, never discarded.
  **There is NO LLM call anywhere in fusion.**
- **Relationships:** two-stage — chunk-level plus a cross-chunk pass per
  document. Nine-type controlled vocabulary. "Co-occurrence is not evidence."
- **Retrieval:** four retrievers — keyword, semantic, graph-aware, and hybrid
  (weighted reciprocal-rank fusion, k=60).
- **RAG:** query classification A/B/C plus concept identification in one LLM
  call; routed retrieval (A/B → graph, C → hybrid); ordered evidence assembly
  (definitions → relationship evidence → spans → chunks); citation validation.

---

## 3. Verified results

### Corpus
10 sources (4 pptx, 4 images, 1 pdf, 1 youtube) · 31 native-text pages,
9 OCR pages, 9 transcript segments · 49 chunks, mean 500 chars ·
131 mentions → 72 concepts (17 multi-source) · 91 relationships ·
13 unconnected concepts · 108 relationship evidence records
(62 chunk-scoped, 46 cross-chunk).

### Manual review (human-annotated, seeded random samples)
| What | n | Precision |
|---|---|---|
| Concepts | 50 | **0.580** |
| Fusion decisions | 15 (11 merges + 4 refusals) | **1.000** |
| Relationships | 40 | **0.875** |

Relationship precision by type: depends_on 1.000 (n=14), requires 0.909 (n=11),
used_for 1.000 (n=4), produces 0.750 (n=4), related_to 1.000 (n=3),
part_of 0.000 (n=2), example_of 1.000 (n=1), causes 0.000 (n=1).

**Interpretation that matters:** the 21 failed concepts are NOT hallucinations.
Zero concepts in the corpus have unverifiable evidence. They are *trivial*
extractions — slide fragments, table row labels, worked numeric examples
(e.g. a concept named "error" defined as "error = 2.76 − 6 = −3.24").
Grounding eliminates fabrication but does not confer significance. These are
separate problems and the system solves only the first.

### Retrieval — 46 queries (15 direct, 20 paraphrase, 11 relationship)
| Retriever | P@1 | P@3 | R@3 | R@5 | Hit@3 | MRR |
|---|---|---|---|---|---|---|
| Keyword | 0.543 | 0.293 | 0.558 | 0.645 | 0.717 | 0.635 |
| Semantic | 0.674 | 0.319 | 0.670 | 0.743 | 0.826 | 0.755 |
| Graph-aware | 0.674 | 0.319 | 0.670 | 0.728 | 0.826 | 0.754 |
| Hybrid | 0.696 | 0.312 | 0.659 | 0.768 | 0.848 | **0.769** |

MRR by query kind:
| Retriever | Direct | Paraphrase | Relationship |
|---|---|---|---|
| Keyword | 0.878 | **0.314** | 0.886 |
| Semantic | 0.922 | **0.544** | 0.909 |
| Graph-aware | 0.922 | 0.542 | 0.909 |
| Hybrid | 0.967 | 0.518 | 0.955 |

**Headline:** the paraphrase column is the real finding — a 0.23 gap where
direct/relationship queries show under 0.05. Graph-aware ties semantic
(0.754 vs 0.755); it does NOT beat it. The paper must not claim otherwise.

### Ablation — full corpus, concept level, all 49 chunks, zero failures
| Configuration | Mentions | Unverifiable | Concepts |
|---|---|---|---|
| Full system | 131 | **0** | 72 |
| − evidence grounding | 294 | **38** | 104 |
| − semantic fusion | 131 | 0 | 82 |
| − cross-document merging | 131 | 0 | 83 |

**Caveat:** ablation is concept-level only. Relationship-level ablation was not
run (quota). Also note the ablation harness omits the semantic retriever, so any
ablation MRR is not comparable to the §V retrieval table.

**Important subtlety:** on the main corpus `dropped_concepts = 0` — the
verification gate never fired, because the grounded prompt produced no
unverifiable output. The evidence that grounding matters lives *entirely* in the
ablation row above. Without it, the paper's headline contribution has no support.

---

## 4. Scope — what was deliberately CUT

These were in early plans and still appear in the paper draft. **They do not
exist.** Any paper text describing them is describing unbuilt software:

- User accounts, authentication, JWT
- PostgreSQL (no relational DB in the system at all)
- Workspaces, workspace isolation, sharing, permissions
- Learning-support features: quiz generation, "explain this differently",
  progress/mastery tracking, text-to-speech, prerequisite navigation UI
- The comparative user study (concept-centric vs document-centric)

---

## 5. Known errors in the current paper draft

Ranked by severity. A reviewer should verify each is fixed.

1. **§3D and Figure 2 claim borderline fusion cases go to "Gemini 2.5" for
   context-aware disambiguation. This is false.** Fusion is entirely
   rule-based after the similarity pre-filter. This misdescribes the paper's
   own contribution, and describes the weaker method.
2. **No reference list exists.** Citations [1]–[21] are used throughout and
   resolve to nothing.
3. **"Gemini 2.5" appears ~5 times in text plus twice in Figure 1 and once in
   Figure 2.** That model was not used and that version does not exist.
   Correct: `gemini-3.6-flash` primary, Groq `gpt-oss-120b` fallback, 95% Groq.
4. **§3C never mentions the evidence gate** — no verbatim span requirement, no
   verification, no discarding. The paper's central mechanism is absent from
   the section that should define it.
5. **Cut scope still present:** §3A "with learning support"; §3F ¶2 (quizzes,
   progress tracking); §3G entirely (PostgreSQL/JWT/workspaces); §3H user
   study; Figure 1 boxes "Learning Support Features", "Persistence & Access",
   "Learning Insights"; Lit Review closing phrase "within a unified educational
   workspace".
6. **§3H claims fusion recall and F1.** Only precision was computed; recall
   requires exhaustive pairwise annotation that was not performed.
7. **§3E names only 3 relation types**; the vocabulary has 9. Also typo
   "The required relation" → *requires*; and "VV"/"EE" should be *V*/*E*.
8. **§3F omits hybrid retrieval** as a method, though it is evaluated and wins.
9. **Figure 2 typo: "Odrant" → "Qdrant".** Figure 2 also has no rejection path,
   so it cannot express a refusal — half the fusion result.
10. **Figure 1 shows 10 stages while §3A says five.**
11. **Table I is a raster image**, not a native table, and labels studies by
    author name while the text cites by number — no mapping between them.
12. **No abstract, no index terms, no IEEE section numbering** (`INTRODUCTION:`
    rather than `I. INTRODUCTION`).
13. The single equation (cosine similarity) is mathematically correct but
    poorly rendered, unnumbered, and omits the 0.80 threshold. Formulae for
    RRF, MRR and P@k are missing entirely though their outputs are reported.

---

## 6. What the paper can and cannot claim

**Can claim,** with evidence:
- Grounding eliminates unverifiable extraction (38 → 0) at ~45% of raw yield.
- Fusion precision 1.00 on both merges and refusals, driven by rule-based
  guards rather than embedding similarity.
- Relationship precision 0.875 overall, 1.000 on the most frequent type.
- Semantic/graph retrieval beats lexical on paraphrase by 0.23 MRR.
- Cross-chunk extraction recovered 46 of 108 relationship evidence records.

**Cannot claim:**
- Any learning outcome, usability, or user-study result.
- That GraphRAG outperforms embedding retrieval (it ties).
- Fusion recall or F1.
- Answer-quality or citation-accuracy scores for the RAG layer (never measured).
- Relationship-level ablation.
- Any timing or cost figure.

---

## 7. Where results are stored

| Result | File |
|---|---|
| Corpus stats | `output/ingestion_result.json`, `output/preprocessed_chunks.json` |
| Mentions | `data/extracted_concepts.json` |
| Concepts + fusion decisions | `data/normalized_concepts.json` (`fusion_decisions`) |
| Relationships | `data/relationships.json` (`evidence[].scope`) |
| Retrieval metrics | `data/evaluation_results.json` |
| Ablation | `data/ablation_results.json`, `data/ablation/<variant>/` |
| Human annotations | `evaluation/reviews/{concepts,fusion,relationships}.json` |
| Query ground truth | `evaluation/queries.json` (46 cases) |

Regeneration: `run_evaluate.py`, `run_review.py`, `_abl_free.py` + `_abl_ng.py`.

---

## 8. How to assess this paper

The paper is a university capstone in IEEE format. Priorities for review:

1. **Does every factual claim match §§1–3 of this document?** The draft has a
   history of describing intended rather than implemented behaviour.
2. **Is the evidence-grounding contribution actually argued?** It is the
   strongest result and was, in the draft reviewed, absent from Methodology.
3. **Are cut features fully removed** from text and figures (§4 above)?
4. **Are limitations stated honestly** — small corpus, 0.58 concept precision,
   self-authored retrieval ground truth, no human-subject evaluation?
5. **Is the graph-vs-semantic tie reported as a tie**, not as a win?

The most interesting thing about this project is a negative-shaped result:
verifiable grounding works exactly as designed and still yields only 58%
useful concepts, because grounding and significance are different problems.
A good paper leads with that rather than hiding it.
