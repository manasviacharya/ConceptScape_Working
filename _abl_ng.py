import json, os, logging
from logging_setup import configure_logging
from evaluation.ablation import variant_settings, variant_dir
import run_extraction, run_normalization

configure_logging(); logging.getLogger().setLevel(logging.INFO)
name = "no_grounding"
out = variant_dir(name); os.makedirs(out, exist_ok=True)
ov = {"extraction_grounded_prompt": False, "require_evidence": False}
with variant_settings(ov, out):
    run_extraction.main()
    run_normalization.main()
ex = json.load(open(os.path.join(out, "extracted_concepts.json")))
nc = json.load(open(os.path.join(out, "normalized_concepts.json")))
print(f"RESULT {name}: mentions={len(ex['concepts'])} "
      f"unverifiable={sum(1 for m in ex['concepts'] if not m.get('evidence_verified_against'))} "
      f"dropped={len(ex.get('dropped_concepts',[]))} concepts={len(nc['concepts'])} "
      f"failed_chunks={len(ex.get('failed_chunks',[]))}")
