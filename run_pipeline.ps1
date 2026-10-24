$ErrorActionPreference = "Stop"
$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { $python = "python" }

& $python run_ingestion.py
& $python run_preprocessing.py
& $python run_extraction.py
& $python run_normalization.py
& $python run_relationships.py
& $python run_build_graph.py
& $python run_index.py
& $python scripts\validate_artifacts.py

Write-Host "ConceptScape pipeline completed and artefacts validated."
