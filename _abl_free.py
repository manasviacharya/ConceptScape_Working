import json, os, shutil, logging
from config import settings
from logging_setup import configure_logging
from evaluation.ablation import variant_settings, variant_dir
import run_normalization

configure_logging(); logging.getLogger().setLevel(logging.WARNING)

FREE = [("full", {}), ("no_fusion", {"fusion_enabled": False}),
        ("no_cross_document", {"normalize_cross_document": False})]

for name, ov in FREE:
    out = variant_dir(name); os.makedirs(out, exist_ok=True)
    src = os.path.join(variant_dir("full"), "extracted_concepts.json")
    if name != "full":
        shutil.copy(src, os.path.join(out, "extracted_concepts.json"))
    with variant_settings(ov, out):
        run_normalization.main()
    ex = json.load(open(os.path.join(out, "extracted_concepts.json")))
    nc = json.load(open(os.path.join(out, "normalized_concepts.json")))
    print(f"{name:<20} mentions={len(ex['concepts']):>4} "
          f"unverifiable={sum(1 for m in ex['concepts'] if not m.get('evidence_verified_against')):>3} "
          f"dropped={len(ex.get('dropped_concepts',[])):>3} "
          f"concepts={len(nc['concepts']):>4}")
