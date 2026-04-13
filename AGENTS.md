# OTERNOS Agent Guardrails

This project is being moved toward a polished personal Spotify-style desktop app.
Do not make random UI framework changes.

## UI Direction

- Current app: legacy Tkinter shell in `oternos/player.py`.
- Future app shell: PySide6/Qt, introduced deliberately in a later phase.
- Existing HTML/PyQt boot screens may remain for compatibility, but do not add new
  HTML/webview UI surfaces unless the user explicitly asks for that exact thing.
- Do not convert features to Electron, React, Flask, browser UI, webview, PyQt,
  PySide, CustomTkinter, or any other stack without an explicit phase/task saying so.

## Phase Discipline

- Phase 1: stabilize current behavior and map boundaries.
- Phase 2: create a new PySide6 shell beside the legacy Tkinter app.
- Later phases: migrate playback, library, search, and sources one at a time.

When asked to improve the UI, first identify which phase is active. Do not
rewrite the whole app or mix UI frameworks opportunistically.

## Source Of Truth

- Edit source files under `oternos/`.
- Avoid editing `dist/void_player/_internal/` except as a temporary emergency fix
  for a user who is immediately running the already-built executable.
- After source fixes, prefer a clean rebuild over hand-patching `dist`.

## Stability Rules

- Keep playback working before changing visuals.
- Keep local library, queue, settings, and source APIs behavior-compatible.
- Do not remove existing functionality during migration.
- Treat `oternos/player.py` as the legacy working implementation and reference it
  when extracting core behavior.
- Do not add more runtime monkey patches unless there is no safer source fix.

