# Graphviz Runtime Assets

This directory is the canonical home for the prebuilt Graphviz binaries that used to live at `c:/x_runner_x/tools/graphviz`. Keeping the payloads inside the `x_make_graphviz_x` repo lets DocumentFactory track ownership, verify checksums, and keep the workspace root free of loose tooling artifacts.

- `win64-12.1.2/` bundles the extracted Graphviz runtime plus the original `.zip` and release metadata JSON generated during the 0.20.15 Change Control program.
- Future Graphviz payloads should land under a new versioned subfolder (`win64-<major.minor.patch>`). Each folder must contain the upstream archive, the extracted runtime, and the JSON manifest produced by `generate_graphviz_metadata.py`.
- When updating these assets, regenerate evidence under `Change Control/0.20.15/evidence/workspace_policy/` (or the current rev) and include a copy of the checksums in the release ticket.
