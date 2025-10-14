# x_make_graphviz_x — Control Room Lab Notes

> "I sketch out every cook before I fire the burner. Graphviz is how I show the crew exactly where each molecule flows."

## Manifesto
x_make_graphviz_x is my Graphviz DOT builder—clusters, graph attributes, SVG export, the works. It lets me wire diagrams as code so the Road to 0.20.2 teams can see pipelines before a single task executes.

## 0.20.2 Command Sequence
Version 0.20.2 tightens the diagram canon. Every graph in this lab now mirrors the Road to 0.20.2 flowchart, annotated with the same precision I reserve for the production line. Deviations are liabilities—erase them before they multiply.

## Ingredients
- Python 3.11+
- Graphviz system binaries (`dot` on PATH) for SVG rendering
- Ruff, Black, MyPy, and Pyright to keep helpers in spec
- Optional: `graphviz` Python package for direct rendering from scripts

## Cook Instructions
1. `python -m venv .venv`
2. `.\.venv\Scripts\Activate.ps1`
3. `python -m pip install --upgrade pip`
4. `pip install -r requirements.txt`
5. `python -m x_make_graphviz_x.tests.example` or your own scripts to generate DOT and SVG outputs

## Quality Assurance
| Check | Command |
| --- | --- |
| Formatting sweep | `python -m black .`
| Lint interrogation | `python -m ruff check .`
| Type audit | `python -m mypy .`
| Static contract scan | `python -m pyright`
| Functional verification | `pytest`

## Distribution Chain
- [Changelog](./CHANGELOG.md)
- [Road to 0.20.2 Control Room Ledger](../x_0_make_all_x/Change%20Control/0.20.2/Road%20to%200.20.2%20Engineering%20Proposal.md)
- [Road to 0.20.2 Engineering Proposal](../x_0_make_all_x/Change%20Control/0.20.2/Road%20to%200.20.2%20Engineering%20Proposal.md)

## Cross-Linked Intelligence
- [x_make_markdown_x](../x_make_markdown_x/README.md) — consumes these diagrams for documentation drops
- [x_make_mermaid_x](../x_make_mermaid_x/README.md) — the sister renderer for Mermaid schematics
- [x_0_make_all_x](../x_0_make_all_x/README.md) — orchestrator references these diagrams when choreographing release phases

## Lab Etiquette
Check in every new diagram helper with matching tests and update the Change Control index with the pipeline it visualizes. Clarity saves lives—and releases.
