"""Create a traceable quality report without mutating graph/source artefacts."""
import json
from pathlib import Path

from quality.report import build_quality_report_from_dir

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    with (ROOT / path).open(encoding="utf-8") as handle:
        return json.load(handle)


report = build_quality_report_from_dir(ROOT / "data")
(ROOT / "data").mkdir(exist_ok=True)
with (ROOT / "data/quality_report.json").open("w", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, ensure_ascii=False)
print("Quality report written to data/quality_report.json")
