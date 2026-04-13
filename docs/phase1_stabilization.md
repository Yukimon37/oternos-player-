# Phase 1 Stabilization Map

Phase 1 is about stopping UI drift and making OTERNOS migration-ready. It is not
the visual redesign phase.

## Decision

OTERNOS will move toward a polished personal Spotify-style desktop app using a
new PySide6/Qt shell in a later phase.

The current Tkinter app remains the working legacy implementation until each
feature is migrated. HTML/webview screens are not the future main app shell.

## Current Runtime Shape

- `oternos/__main__.py`
  - process entry point
  - boot/init orchestration
  - creates the Tk root
  - instantiates `VoidPlayer`
  - loads runtime patches
- `oternos/player.py`
  - legacy Tkinter shell
  - global app state
  - local playback controls
  - library, playlists, queue, settings
  - many Tk views and widgets
  - bridge startup
  - feature view mounting
- `oternos/audio.py`
  - pygame-backed playback engine
  - load/play/pause/seek/stop/duration
- `oternos/streaming.py`
  - API clients for Spotify, SoundCloud, YouTube, Deezer, Archive, Bandcamp
- `oternos/mixins/*`
  - source-specific feature behavior attached to `VoidPlayer`
  - many methods still directly manipulate Tk widgets and shared app state
- `oternos/netstream.py`
  - LAN streaming server/client plus its own Tk view
- `oternos/bridge.py`, `oternos/sc_bridge.py`
  - HTTP bridges for HTML/player integrations
- `oternos/patches/*`
  - runtime monkey patches loaded after `VoidPlayer` construction

## Stabilization Findings

- The app has one large legacy UI object: `VoidPlayer`.
- Playback state and UI state are tightly coupled.
- Source logic often directly updates Tk labels, buttons, and frames.
- Runtime patches make behavior harder to reason about and should shrink over time.
- The packaged `dist` tree has been patched manually for emergency fixes; source
  must remain the long-term truth.
- Current boot flow includes HTML/PyQt paths, Tk fallback boot, and an eDEX-style
  Tk init overlay. Do not add more boot/UI variants during stabilization.
- The current shell used by this agent cannot run `python` or `py`; import/compile
  verification needs a Python-enabled shell or a clean `build.bat` run.

## Reusable Core Candidates

Extract these first, in this order:

1. `PlaybackController`
   - wraps `AudioEngine`
   - exposes play, pause, resume, stop, seek, next, previous
   - emits state changes instead of touching widgets
2. `LibraryStore`
   - owns library track list
   - scan/add/remove/save/load
   - no Tk imports
3. `QueueController`
   - owns auto queue, manual queue, shuffle, repeat
   - returns next/previous track decisions
4. `SettingsStore`
   - owns defaults and JSON persistence
   - no Tk imports
5. `SourceRegistry`
   - normalizes local, SoundCloud, YouTube, Spotify, Deezer, Archive, Bandcamp
   - exposes common search/play result shapes
6. `AppEvents`
   - small pub/sub or callback layer for UI updates
   - lets legacy Tk and future Qt subscribe to the same state changes

## Target Module Layout

```text
oternos/
  core/
    __init__.py
    events.py
    models.py
    playback.py
    library.py
    queue.py
    settings.py
    sources.py
  ui_tk/
    legacy adapter around current VoidPlayer pieces, later
  ui_qt/
    future PySide6 shell, later
```

Do not create all of this at once unless the phase calls for it. Start with
small adapters that preserve the current app.

## Migration Acceptance Criteria

Phase 1 is complete when:

- startup crashes are fixed in source
- stream/playback import errors are fixed in source
- future agents have explicit guardrails
- current architecture is mapped
- next extraction order is clear
- no new UI framework has been added opportunistically

## Phase 1B Progress

Started the settings extraction:

- Added `oternos/core/settings.py`.
- Added `DEFAULT_SETTINGS`, `build_default_settings()`, and `merge_settings()`.
- Updated `VoidPlayer._load_data()` to use `merge_settings()`.
- Preserved the existing `.voidplayer.json` format.
- Left full save/load ownership in `VoidPlayer` for now to avoid a broad behavior
  change.

Next settings step:

- Move JSON read/write into a small `SettingsStore`/app-data helper after the
  current extraction has been verified in a Python-enabled shell.

## Phase 1C Progress

Started the queue extraction:

- Added `oternos/core/queue.py`.
- Added `promote_manual_next()` for the legacy manual-queue drain behavior.
- Added `choose_next_position()` for normal/shuffle next-track decisions.
- Added `choose_previous_position()` for previous-track decisions.
- Updated `VoidPlayer._next()` and `VoidPlayer._prev()` to use these helpers.
- Left queue list ownership, UI refreshes, and actual playback calls in
  `VoidPlayer` for now.

Preserved behavior:

- Manual queue still drains before auto queue.
- Manual tracks are inserted immediately after the current queue position.
- Shuffle still avoids replaying the same queue position when possible.
- Normal next/previous still wrap around the queue.

Small stability improvement:

- Previous-track on an empty queue now exits cleanly instead of attempting a
  modulo operation on an empty list.

Next queue step:

- Introduce a small `QueueController` object only after the helper functions are
  verified, then migrate queue mutations such as clear, add, remove, reorder,
  and play-single one at a time.

## Phase 1C Continued

Moved more queue mutation rules into `oternos/core/queue.py`:

- `clear_all()`
- `clear_manual()`
- `reorder_items()`
- `adjust_position_after_reorder()`
- `activate_manual_item()`
- `remove_manual_item()`
- `remove_auto_item()`
- `add_manual_item()`

Updated legacy `VoidPlayer` queue methods to use those helpers while keeping
all Tkinter refreshes, status labels, and playback calls in `player.py`.

Small stability improvement:

- Removing the last auto-queue item now resets `queue_pos` to `-1` instead of
  leaving it pointed at an empty queue.

Deferred:

- Library removal/remapping still lives in `VoidPlayer._rm_from_lib()` because
  that touches library indices, playlists, queue, current track state, engine
  stop behavior, persistence, and UI refreshes together.

## Phase 1D Progress

Started the playback extraction:

- Added `oternos/core/playback.py`.
- Added `PlaybackController`, a thin adapter around the existing `AudioEngine`.
- Added `PlaybackState`, a small state snapshot shape for future UI shells.
- Added an `AudioEngineLike` protocol to describe the engine surface without
  importing Tkinter or pygame.
- Added `self.playback = PlaybackController(self.engine)` in `VoidPlayer`.

Updated low-risk legacy paths to call the adapter:

- local library track load/play
- local pause/resume
- local stop in `_stop_all_sources()`
- local seek-to-start behavior in `_prev()`

Preserved behavior:

- `AudioEngine` is still the actual pygame-backed engine.
- `VoidPlayer` still owns UI updates, source state, crossfade, EQ swap, and
  stream-specific playback.
- Streaming mixins still call `self.engine` directly for now.

Next playback step:

- After verification, migrate more engine calls to `self.playback` in small
  clusters: seek paths, volume paths, then source mixins. Do not move
  `_play_item()` orchestration until the controller API is proven.

## Phase 1D Continued

Migrated player-owned seek paths to `PlaybackController`:

- debounced relative seek
- main progress-bar release seek
- mini-player progress seek
- cue-point jump
- A-B repeat loop seek
- bookmark jump

Result:

- `oternos/player.py` no longer calls `self.engine.seek(...)` directly.
- Spotify seek paths still call `sp_api.seek(...)`.
- Source mixins and network controls still call engine seek directly for now.

Next playback step:

- Migrate volume paths in `player.py` to `self.playback.set_volume(...)`.
- Leave fades/crossfade and source mixins until simple volume controls are
  verified.

## Phase 1D Volume Progress

Migrated simple player-owned volume controls to `PlaybackController`:

- main window Up/Down volume shortcuts
- player bar volume press/drag/scroll
- `_set_vol()` helper
- mini-player mouse wheel volume
- custom hotkey volume up/down actions

Intentionally left direct `engine.set_volume(...)` in timing/effect internals:

- sleep fade
- crossfade fade-out/fade-in
- track gain adjustment

Those paths change volume continuously as part of effects and should be migrated
only after simple controls are verified.

## Phase 2A Progress

Added a source-run PySide6 prototype shell beside the legacy Tkinter app:

- `oternos/qt_main.py`
- `oternos/ui_qt/__init__.py`
- `oternos/ui_qt/shell.py`
- `docs/phase2_qt_shell.md`

This shell is static and does not replace the working app.

## Phase 2B Progress

Restyled the Qt prototype toward the current OTERNOS identity:

- black/white void palette
- terminal-style chips, metadata, and source status rows
- dashboard signal bus with static meter bars
- stronger now-playing command panel
- compact bottom player bar with static progress and volume controls

Next Qt step:

- Wire read-only app state into the shell through small core-facing adapters.
- Start with current track metadata, queue preview, library counts, source
  status, playback position, and volume.

## Phase 2C Progress

Added the first read-only state bridge:

- `oternos/core/app_state.py`
- `tests/test_core_app_state.py`

The Qt shell now reads the existing saved `.voidplayer.json` state without
constructing the legacy Tkinter player. It can display saved library count,
playlist count, recent history/current-ish track, repeat/shuffle/flow mode,
source status, and a local library queue preview.

Deferred:

- live playback position
- live volume
- controlling playback from Qt
- keeping the Qt snapshot refreshed while the legacy app is open

## Phase 2D Progress

Made the Qt state bridge refreshable while keeping it read-only:

- Added `snapshot_file_marker()` to detect saved-state file changes cheaply.
- Added a 3-second Qt timer that reloads only when `.voidplayer.json` changes.
- Added a `[ REFRESH ]` button for manual reloads.
- Preserved the active Qt page across snapshot refreshes.

Next Qt step:

- Create a small runtime status channel for live playback state instead of
  relying only on saved JSON. Start read-only with current track, position,
  volume, paused/playing state, and source.

## Phase 2E Progress

Added the first live read-only runtime bridge:

- `oternos/core/runtime_state.py`
- `tests/test_core_runtime_state.py`

The legacy Tkinter app now publishes `.voidplayer_runtime.json` once per second
while it is running. The Qt shell reads this file and prefers it over saved
state when it is fresh.

Runtime fields now available to Qt:

- active source
- status
- playing/paused state
- current position
- duration
- volume
- current track title, artist, album, source, and path

Still deferred:

- Qt playback controls
- write/command channel
- final migration away from Tkinter

## Phase 2F Progress

Added the first controlled command channel:

- `oternos/core/runtime_commands.py`
- `tests/test_core_runtime_commands.py`

The Qt shell now writes command requests, and the legacy Tkinter app polls and
executes only a small whitelist:

- play/pause
- next
- previous
- relative seek
- set volume

Qt still does not own playback internals. It asks the running legacy app to do
the work.

Next Qt step:

- Expand the Qt player bar polish around the now-functional controls.
- Then add read-only queue detail before attempting queue mutation commands.

## Phase 2G Progress

Polished the functional Qt player bar and live-state UX:

- live/stale/offline chips
- disabled controls when the legacy runtime bridge is unavailable
- current time and total time labels
- volume percent label
- clearer saved snapshot vs live runtime wording

Next Qt step:

- Add a richer read-only queue surface before adding queue mutation commands.

## Phase 2H Progress

Added live read-only queue details to the runtime bridge:

- queue count
- manual queue count
- current queue position
- live queue preview

The Qt shell now renders a live queue panel with the current item marked `NOW`.
It still falls back to saved preview data when the legacy app is offline.

Next Qt step:

- Add safe queue commands one at a time, starting with playing a selected queue
  item.

## Phase 2I Progress

Added the first queue command:

- `play_queue_position`

The Qt queue panel can now ask the running legacy player to play a visible live
queue item. The legacy app validates the queue position and routes playback
through its existing `_play_item()` behavior.

Safety note:

- The legacy app now records the existing command id at startup so an old command
  file is not replayed accidentally.

Still deferred:

- remove queue item
- clear queue
- reorder queue

## Phase 2J Progress

Added a safe queue removal command:

- `remove_queue_position`

The Qt queue panel can now ask the running legacy player to remove a non-current
visible queue item. The legacy app validates the queue position, refuses to
remove the active queue item, and uses its existing `_queue_remove()` behavior.

Still deferred:

- clear queue
- reorder queue
- removing/skip-removing the current item

## Phase 2K Progress

Polished the live Now Playing surface:

- playback progress percent
- runtime link/source/volume/queue telemetry
- runtime-derived signal meter bars
- quieter stale/offline visual fallback

Next Qt step:

- Add real artwork handoff or a dedicated lyrics/readout panel before moving to
  heavier queue mutations.

## Phase 1E Progress

Started the library extraction:

- Added `oternos/core/library.py`.
- Added `filter_existing_tracks()` for loading saved library entries whose files
  still exist.
- Added `remap_indices_after_library_removal()` for queue/playlist index lists.
- Added `remap_playlists_after_library_removal()`.
- Added `adjust_queue_pos_after_library_removal()` to preserve the legacy queue
  position clamp after library removal.

Updated low-risk legacy paths:

- `VoidPlayer._load_data()` now uses `filter_existing_tracks()`.
- `VoidPlayer._rm_from_lib()` now uses core helpers for playlist and queue
  remapping.

Small stability improvement:

- Malformed saved library data such as `"library": null` now loads as an empty
  library instead of breaking startup.

Deferred:

- Import scanning and metadata creation still live in `VoidPlayer`.
- Bulk duplicate cleanup still lives in `VoidPlayer`.
- Removing the currently playing track still owns UI reset and engine stop in
  `VoidPlayer`.

## Phase 1F Progress

Added a stdlib `unittest` safety net for the extracted core helpers:

- `tests/test_core_settings.py`
- `tests/test_core_queue.py`
- `tests/test_core_library.py`
- `tests/test_core_playback.py`

Covered:

- settings default-copy behavior and saved-settings merge behavior
- queue next/previous/manual/reorder/remove/clear/add decisions
- library saved-track filtering and index remapping
- playback controller delegation using a fake engine

Run from a Python-enabled shell:

```bat
py -3.12 -m unittest discover -s tests
```

or:

```bat
python -m unittest discover -s tests
```

Current limitation:

- This Codex shell still cannot run `python` or `py`, so these tests have been
  written and statically inspected but not executed here.

## Next Phase Entry Point

Phase 2 should create a minimal `oternos/ui_qt/` shell using static data:

- sidebar
- top search/header
- central routed content area
- bottom playback bar
- dark OTERNOS design system

It should not migrate all playback yet. It should prove the product direction
without disturbing the working Tkinter app.

## Phase 2A Started

Added a static PySide6 prototype beside the legacy Tkinter app:

- `oternos/qt_main.py`
- `oternos/ui_qt/__init__.py`
- `oternos/ui_qt/shell.py`
- `docs/phase2_qt_shell.md`

This prototype is launched separately and does not affect `python -m oternos` or
the current packaged app.

## Phase 2L Progress

The Qt shell now receives album-art metadata through the same bridge that feeds
playback status:

- `TrackSummary` and `RuntimeTrack` include `art_path` and `art_url`.
- The legacy player publishes local cover paths and known stream cover URLs.
- The Qt Now Playing panel and bottom player bar render local cover files when
  an `art_path` is available.

Remote cover URLs are intentionally not fetched yet. That keeps this step local
and low risk before adding cache/download behavior.

## Phase 2M Progress

The Qt shell now fetches remote cover URLs asynchronously through QtNetwork and
caches valid image data under `.voidplayer_cache/art` in the user's home
directory. The main Now Playing panel and bottom player bar can render cached
stream covers after the fetch completes.

This still leaves cache pruning and cover art inside recent-track cards for a
later pass.

## Phase 2N Progress

Cover art is now part of the broader Qt shell instead of only the Now Playing
surface:

- Recent Signals cards render thumbnails.
- Live and saved queue rows render thumbnails.
- The bottom player bar shares the same thumbnail renderer.

This keeps the shell feeling more like a music collection while playback and
queue ownership remain with the legacy player.

## Phase 2O Progress

The Qt sidebar now routes to distinct page surfaces instead of changing only the
title text:

- Home dashboard
- Search surface
- Library preview
- Playlists overview
- Sources matrix
- Now Playing focus view
- Queue command view
- Settings/state view

The read-only snapshot now exposes a small library preview and playlist names so
those pages can be useful without migrating ownership away from the legacy
player.

## Phase 2P Progress

The Qt Search page now filters the read-only saved track preview as text is
entered. The top search field also opens the Search page when Enter is pressed.

The saved library preview now exposes up to 48 tracks, which gives the Search
and Library pages more useful data while still keeping this phase read-only.

## Phase 2Q Progress

Qt can now request playback of saved local-library tracks:

- `play_library_path` was added to the runtime command whitelist.
- Track cards expose a `PLAY` button when the legacy player is live.
- The legacy player resolves the requested file path against its current
  library and plays it through the existing local playback path.
- Recent-history cards now resolve back to matching local-library tracks when
  possible, so cards with title/artist-only history can still be playable.

This is the first card-level action from Qt while preserving the legacy player
as the playback owner.

## Phase 2R Progress

Qt track cards can now queue saved local-library tracks:

- `add_library_path_to_queue` was added to the runtime command whitelist.
- Cards show `PLAY` and `ADD` actions.
- The legacy player resolves the path and reuses `_add_to_queue()`.

This adds useful queue control without moving queue ownership into Qt yet.

## Phase 2S Progress

The Qt shell now gives visible feedback when commands are sent:

- A top-bar action chip shows command status.
- Card and queue actions report sent/offline/failed states.
- The chip clears back to `READY` after a short delay.

The feedback is intentionally optimistic; actual playback and queue truth still
come from the legacy runtime snapshot.

## Phase 2T Progress

The legacy player now acknowledges commands in the live runtime snapshot:

- A handled command records id, action, success, message, and timestamp.
- Qt matches the acknowledgement against the command it sent.
- The action chip upgrades from optimistic `SENT` states to confirmed legacy
  states such as `PLAY HANDLED`, `ADD HANDLED`, or `TRACK NOT FOUND`.

This closes the loop on the current command bridge without changing playback
ownership.

## Phase 2U Progress

Qt cards are now queue-aware:

- Runtime state includes full queued local paths.
- Cards can show `NOW` for the active local track.
- Cards can show `QUEUED` for local tracks already in the queue.
- `ADD` disables when the card is already current or queued.

This gives the new shell clearer music-app behavior without migrating queue
ownership yet.
