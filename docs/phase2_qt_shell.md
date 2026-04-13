# Phase 2 Qt Shell Prototype

Phase 2 introduces a PySide6 shell beside the legacy Tkinter app. It can read
live state and send a small set of playback commands, but it does not replace
`python -m oternos`.

## Files

- `oternos/qt_main.py`
- `oternos/core/app_state.py`
- `oternos/core/runtime_commands.py`
- `oternos/core/runtime_state.py`
- `oternos/ui_qt/__init__.py`
- `oternos/ui_qt/shell.py`

## Run

From a Python environment with PySide6 installed:

```bat
py -3.12 -m oternos.qt_main
```

or:

```bat
python -m oternos.qt_main
```

If PySide6 is missing, the prototype exits with a short install message.

## Scope

Included:

- left sidebar navigation
- top search/header bar
- central dashboard content area
- persistent bottom player bar
- static source/status/queue/card panels
- dark OTERNOS visual system
- Phase 2B OTERNOS styling pass:
  - black/white void palette matching the current player identity
  - terminal-style status chips and metadata rows
  - signal/meter band across the dashboard
  - stronger now-playing command panel
  - tighter bottom playback bar

Not included yet:

- real playback
- source search
- packaging into `void_player.exe`
- replacing the Tkinter app

## Packaging Note

`void_player.spec` currently excludes `PySide6`, so this prototype is source-run
only until the project intentionally switches packaging targets.

## Phase 2B Notes

The prototype now has enough visual direction to use as the target shell for the
next migration work. The next step is not another visual rewrite; it is wiring
read-only app state into the shell:

- current track metadata
- queue preview
- library counts
- source health
- playback position and volume snapshots

Keep the legacy Tkinter player as the working app until the Qt shell can display
real state reliably.

## Phase 2C Notes

Added the first read-only state bridge for the Qt shell:

- `load_app_snapshot()` reads the existing `.voidplayer.json` file.
- The Qt shell now displays saved library count, playlist count, repeat/shuffle
  mode, source status, recent history, and a local queue preview.
- The shell still does not mutate state and does not control playback.

Next read-only state step:

- Move from one startup snapshot to a refreshable snapshot.
- Add a small timer/manual refresh so changes made by the legacy player can show
  in the Qt shell while both are open.

## Phase 2D Notes

The Qt shell now refreshes saved state without taking control of playback:

- `snapshot_file_marker()` detects `.voidplayer.json` changes cheaply.
- The shell checks the marker every 3 seconds.
- The dashboard rebuilds only when saved state changes.
- A `[ REFRESH ]` button forces a manual state reload.
- The active page is preserved across refreshes.

Still deferred:

- live in-memory playback state
- playback controls
- write access from Qt

## Phase 2E Notes

Added the first live read-only runtime bridge:

- The legacy Tkinter player writes `.voidplayer_runtime.json` once per second
  while it is running.
- The runtime snapshot includes source, status, play/pause state, position,
  duration, volume, and current track metadata.
- The Qt shell reads that runtime file and prefers live data when it is fresh.
- If the legacy app is not running, Qt falls back to saved `.voidplayer.json`
  state.

Still deferred:

- replacing the Tkinter shell

## Phase 2F Notes

Added the first command bridge from Qt to the legacy player:

- Qt writes `.voidplayer_command.json` command requests.
- The legacy player polls the command file every 250ms.
- Only whitelisted commands are accepted:
  - play/pause toggle
  - next
  - previous
  - relative seek
  - set volume
- Qt still does not touch the audio engine directly.

Still deferred:

- queue editing from Qt
- library/search commands from Qt
- replacing the Tkinter shell
- packaging the Qt shell into the built executable

## Phase 2G Notes

Polished the now-functional Qt player bar:

- Top status chips now distinguish live, stale, and offline runtime state.
- Playback controls disable when the legacy app is not live.
- The bottom bar now shows current time, total time, and volume percent.
- The progress and volume sliders disable when they cannot safely send commands.
- The now-playing panel labels live runtime vs saved snapshot state more clearly.

Still deferred:

- richer queue display
- queue mutation commands
- polished album art/visualizer surfaces

## Phase 2H Notes

Added live read-only queue detail:

- Runtime state now includes queue count, manual queue count, current queue
  position, and a live queue preview.
- The Qt queue panel now prefers live queue data when the legacy player is
  running.
- The current queue item is marked `NOW`.
- Saved queue preview remains the fallback when the legacy runtime bridge is
  offline.

Still deferred:

- queue mutation commands
- playing a specific queue item from Qt
- drag/reorder from Qt

## Phase 2I Notes

Added the first queue command:

- The Qt queue preview now has a `PLAY` button for non-current live queue items.
- Qt sends a `play_queue_position` command with the queue position.
- The legacy player validates the position and plays it through the existing
  `_play_item()` path.
- The legacy player ignores any old command file at startup so stale commands do
  not replay when the app opens.

Still deferred:

- remove from queue
- clear queue
- reorder queue
- saved/offline queue commands

## Phase 2J Notes

Added the second queue command:

- The Qt queue preview now has a `DROP` button for non-current live queue items.
- Qt sends a `remove_queue_position` command with the queue position.
- The legacy player validates the position, refuses to remove the current item,
  and routes removal through the existing `_queue_remove()` path.

Still deferred:

- removing the currently playing queue item
- clear queue
- reorder queue
- saved/offline queue commands

## Phase 2K Notes

Polished the live Now Playing surface:

- Added a playback telemetry strip inside the main Now Playing panel.
- The telemetry strip shows progress percent, live link state, source, volume,
  and queue count.
- The dashboard signal meters now derive their bars from runtime state instead
  of staying fully static.
- Offline/stale mode still renders a quieter fallback signal.

Still deferred:

- real album art handoff to Qt
- animated visualizer canvas
- lyric panel in Qt

## Phase 2L Notes

Started real album-art handoff:

- Saved track summaries now preserve `art_path` and `art_url`.
- Live runtime snapshots now preserve `art_path` and `art_url` for the current
  track and queue preview.
- The legacy player publishes local cover paths and known stream cover URLs
  through the runtime bridge.
- The Qt shell now renders local cover files in the main Now Playing panel and
  bottom player bar.
- Remote cover URLs are surfaced as metadata, but Qt does not fetch remote
  images yet.

Still deferred:

- downloading/caching remote stream art for Qt
- larger visualizer canvas
- lyrics and richer source pages

## Phase 2M Notes

Added remote cover loading for the Qt shell:

- The Qt shell now uses QtNetwork to fetch remote cover URLs asynchronously.
- Downloaded covers are validated as images before being written to disk.
- Cached covers are stored under `.voidplayer_cache/art` in the user's home
  directory.
- The Now Playing art tile and bottom player bar render cached stream covers
  after the download finishes.
- The art tile now reports `COVER LOADING`, `COVER CACHED`, or `COVER BLOCKED`
  for remote artwork.

Still deferred:

- pruning old cached covers
- showing cover art inside recent-track cards
- richer animated visualizer canvas

## Phase 2N Notes

Spread cover art through more of the Qt shell:

- Recent Signals cards now include cover thumbnails.
- Live queue rows now include thumbnails beside the queue marker.
- Saved/offline queue fallback rows also show thumbnails when art is available.
- The bottom player bar now uses the same shared thumbnail renderer as the
  rest of the shell.
- Remote cover URLs discovered in recent or queue rows can trigger the same
  background cache path as Now Playing.

Still deferred:

- pruning old cached covers
- animated visualizer canvas
- richer dedicated Library and Source pages

## Phase 2O Notes

Made sidebar routes distinct:

- `Home` keeps the full dashboard.
- `Search` has a search-focused surface with source health and recent matches.
- `Library` has its own collection preview using saved local tracks.
- `Playlists` lists saved playlist names from the read-only snapshot.
- `Sources` shows source cards plus the live Now Playing handoff.
- `Now Playing` focuses on the art/telemetry panel, queue, and recent signals.
- `Queue` gets a larger queue view plus live bridge controls.
- `Settings` shows theme, playback state, bridge state, and snapshot paths.

Snapshot additions:

- `AppSnapshot.library_preview`
- `AppSnapshot.playlist_names`

Still deferred:

- real search execution from Qt
- full library pagination
- playlist editing from Qt
- dedicated source-specific views

## Phase 2P Notes

Made Search interactive inside the Qt shell:

- The Search page now filters saved local, recent, and queue-preview tracks as
  the user types.
- The top search field can jump directly into the Search page when Enter is
  pressed.
- Search state is kept inside the Qt shell and survives normal live-state
  refreshes.
- The saved library preview now exposes up to 48 tracks to give Search and
  Library more useful read-only data.

Still deferred:

- executing new stream searches from Qt
- opening a searched track from Qt
- full library pagination and sorting

## Phase 2Q Notes

Added local-library play from Qt:

- Runtime commands now allow `play_library_path`.
- Track cards now show a `PLAY` button.
- The button is enabled only when the legacy player is live and the track points
  at a local saved file.
- The legacy player resolves the requested path against its current library,
  builds a single-item queue, and plays through the existing `_play_item()` path.
- Recent-history entries now resolve back to matching local-library tracks so
  Home/Search cards can still play even when history saved only title/artist.

Still deferred:

- add-to-queue from Qt cards
- playing stream search results from Qt
- playlist editing from Qt

## Phase 2R Notes

Added local-library queueing from Qt cards:

- Runtime commands now allow `add_library_path_to_queue`.
- Track cards now show `PLAY` and `ADD` actions side by side.
- `ADD` resolves the saved local path in the legacy player and routes through
  the existing `_add_to_queue()` behavior.
- Queue behavior remains owned by the legacy app, including the existing rule
  that adding a track can start playback if nothing is currently playing.

Still deferred:

- visual feedback after a card is queued
- add-to-playlist from Qt cards
- stream-result playback from Qt

## Phase 2S Notes

Added command feedback in the Qt shell:

- The top bar now includes an action/status chip.
- Card and queue actions report `PLAY SENT`, `ADD SENT`, `QUEUE PLAY SENT`,
  `DROP SENT`, `COMMAND OFFLINE`, or `COMMAND FAILED`.
- The action chip updates in-place and clears back to `READY` after a short
  delay.
- The feedback is optimistic; the legacy runtime snapshot still remains the
  source of truth after the command is processed.

Still deferred:

- per-card queued badges
- command acknowledgements from the legacy player
- add-to-playlist from Qt cards

## Phase 2T Notes

Added command acknowledgements from the legacy player:

- Runtime snapshots now include `last_command` acknowledgement data.
- The legacy player records command id, action, success flag, message, and
  handled timestamp after processing a Qt command.
- The Qt shell remembers the command id it sent and upgrades optimistic
  `SENT` feedback into legacy-confirmed messages like `PLAY HANDLED`,
  `ADD HANDLED`, `TRACK NOT FOUND`, or `DROP REFUSED`.
- Failed/refused acknowledgements render as an offline/error chip.

Still deferred:

- per-card queued badges
- command history panel
- add-to-playlist from Qt cards

## Phase 2U Notes

Added queue-aware card states:

- Runtime snapshots now include `queue_paths` for the live local queue.
- The legacy player publishes queued local file paths from both the active queue
  and manual queue.
- Qt track cards now show `NOW` when the card is the current live track.
- Qt track cards now show `QUEUED` when the card already exists in the live
  queue.
- The `ADD` button changes to `NOW` or `QUEUED` and disables when the track is
  already current or queued.

Still deferred:

- add-to-playlist from Qt cards
- full queue reorder from Qt
- stream-result playback from Qt

## Phase 2V Notes

Added playlist saving from Qt cards:

- Runtime commands now allow `add_library_path_to_playlist`.
- Local Qt track cards now include a `LIST` action when saved playlists exist.
- If there is one saved playlist, Qt sends the track there directly.
- If there are multiple saved playlists, Qt opens a small playlist chooser.
- The legacy player resolves the local path, updates the selected playlist,
  saves `.voidplayer.json`, refreshes the legacy playlist sidebar, and returns
  acknowledgements such as `PLAYLIST SAVED` or `ALREADY SAVED`.

Still deferred:

- full queue reorder from Qt
- stream-result playback from Qt
- creating and editing playlists entirely inside Qt

## Phase 2W Notes

Made command behavior easier to read inside the Qt shell:

- The Settings page now includes a persistent `Command Bridge` panel.
- The panel shows live link state, pending command action, last legacy
  acknowledgement, and current action readiness.
- The readiness list distinguishes working local/queue/playlist controls from
  stream playback, which remains a later phase.
- Qt now schedules short follow-up refreshes after sending a command so
  acknowledgements and card states update faster than the normal background
  refresh interval.

Still deferred:

- full queue reorder from Qt
- stream-result playback from Qt
- packaging the Qt shell as its own exe

## Phase 2X Notes

Shifted the Qt shell from clean Spotify-style polish toward a cyber command
deck aesthetic:

- Reworked the Qt stylesheet around a darker green terminal palette with neon
  cyan, warning yellow, and danger red status states.
- Tightened panel/button radii and borders so the shell reads more like a
  control surface than a soft media app.
- Updated navigation, top-bar, dashboard, source, queue, and card labels toward
  VOIDNET/vault/trace language.
- Added scanline separators and a `CYBER ROUTE MAP` dashboard strip that shows
  live bridge, source, queue, volume, and last acknowledgement state.
- Kept the existing Qt bridge, playback commands, queue state, and playlist
  command behavior intact.

Still deferred:

- animated cyber visualizer canvas
- full queue reorder from Qt
- stream-result playback from Qt
- packaging the Qt shell as its own exe

## Phase 2Y Notes

Added Uiverse-inspired cyber button styling to the Qt shell:

- Translated the web/CSS button direction into PySide6 QSS styles instead of
  adding HTML or webview UI.
- Local card actions now use distinct cyber button treatments:
  - `PLAY` uses a bright filled signal button.
  - `ADD` uses a neon outlined command button.
  - `LIST` uses a yellow vault/save button.
  - Queue `DROP` uses a red danger button.
- Disabled states still show clearly when the legacy player is offline or a
  command cannot run.

Still deferred:

- animated button effects beyond Qt stylesheet hover/pressed states
- full queue reorder from Qt
- stream-result playback from Qt

## Phase 2Z Notes

Corrected the cyber aesthetic back to the OTERNOS black-and-white identity:

- Removed the neon green/cyan/yellow/red palette from the Qt shell stylesheet.
- Kept the cyber command-deck structure, scanlines, route map, and sharper
  Uiverse-inspired button shapes.
- Converted action states to monochrome contrast: white primary actions, white
  outlined secondary actions, gray muted/disabled states, and black panels.
- Preserved all command bridge behavior and playback controls.

Still deferred:

- animated monochrome visualizer canvas
- full queue reorder from Qt
- stream-result playback from Qt

## Phase 2AA Notes

Added a native monochrome cyber visualizer to the Qt Now Playing surface:

- The visualizer is a PySide6 painted widget, not an HTML/webview surface.
- It uses only the black-and-white OTERNOS palette.
- It animates from the live runtime snapshot, moving more actively while the
  legacy player is live and playing.
- It displays a grid, scanline, waveform bars, live/offline state, and
  position/duration text.

Still deferred:

- real audio-frequency FFT data from the playback engine
- full queue reorder from Qt
- stream-result playback from Qt

## Phase 2AB Notes

Added a dedicated Visualizer page to the Qt shell:

- The sidebar now includes `Visualizer`.
- The page shows a larger monochrome signal canvas, live/offline bridge state,
  current track trace metadata, position/duration, volume, queue count, and the
  command bridge panel.
- The same native PySide6 visualizer widget can render at different sizes, so
  the compact Now Playing visualizer and full Visualizer page share one code
  path.

Still deferred:

- real audio-frequency FFT data from the playback engine
- full queue reorder from Qt
- stream-result playback from Qt

## Phase 2AC Notes

Ported more of the legacy visualizer language into the Qt shell:

- The native `CyberVisualizer` now supports multiple monochrome modes:
  - spectrum scope
  - radar sweep
  - frequency ring
  - circuit lines
- The Visualizer page shows the large spectrum scope plus smaller radar, ring,
  and circuit panels inspired by the legacy `cyberui.py` widgets.
- All modes remain PySide6-painted widgets and keep the black-and-white OTERNOS
  identity.

Still deferred:

- real audio-frequency FFT data from the playback engine
- user-selectable visualizer presets
- full queue reorder from Qt
- stream-result playback from Qt

## Phase 2AD Notes

Made the Qt Visualizer page more advanced:

- Added user-selectable visualizer presets for the large canvas:
  - spectrum
  - waveform scope
  - frequency ring
  - radar sweep
  - circuit lines
  - node graph
  - data burst
- Added native Qt renderers for node graph, data burst, and waveform scope.
- Expanded the Visualizer page's preview stack so it shows the broader legacy
  visualizer family at once.
- Preserved the black-and-white palette and avoided adding webview/HTML UI.

Future web/library path:

- Qt `QOpenGLWidget` or GPU libraries such as VisPy/ModernGL could power true
  shader-style visualizers later, but they should be introduced as a deliberate
  packaging phase.

Still deferred:

- real audio-frequency FFT data from the playback engine
- GPU/OpenGL visualizer backend
- full queue reorder from Qt
- stream-result playback from Qt

## Phase 2AE Notes

Started separate Qt shell packaging:

- Added `oternos_qt.spec` for building the PySide6 shell as its own executable.
- Added `build_qt.bat` to build only `dist\oternos_qt\oternos_qt.exe`.
- The existing `void_player.spec` and `build.bat` remain the legacy player
  packaging path.
- `build_qt.bat` does not delete `dist\void_player`, so the legacy player stays
  available as the playback engine while the Qt shell is tested.
- Updated `oternos/qt_main.py` so the Qt entry point can import correctly when
  frozen by PyInstaller.

Run:

```bat
build_qt.bat
```

Launch:

```bat
dist\oternos_qt\oternos_qt.exe
```

Still deferred:

- building and smoke-testing the Qt exe on this machine
- deciding whether a future launcher should open both legacy and Qt processes
- replacing the legacy player shell

## Phase 2AF Notes

Fixed Qt shell transport issues found in the packaged exe:

- Qt-initiated local `PLAY` now builds a full-library queue context instead of
  a one-track queue, so `NEXT` and `PREV` have meaningful tracks to move to.
- Runtime `next` and `previous` commands now call the legacy skip methods with
  `force=True`; `PREV` skips back instead of restarting the current song when
  playback is past the normal restart threshold.
- Runtime snapshots now infer `library` source and duration from the current
  local track if the legacy `_active_source` label is stale.
- The Qt shell now refreshes live runtime state every second so progress
  percentage and player bar movement update promptly in the packaged shell.

Still deferred:

- rebuilding both packaged exes after this source fix
- real audio-frequency FFT data from the playback engine
- replacing the legacy player shell

## Phase 2AG Notes

Fixed Visualizer page issues found during Qt exe testing:

- Runtime snapshots now include a clamped 48-band `visualizer_bars` signal from
  the legacy player's existing visualizer/FFT pipeline.
- The legacy player publishes runtime state faster while music is playing so the
  Qt visualizer receives fresher signal data.
- The Qt runtime timer switches to a faster refresh while the Visualizer page is
  active and playback is live.
- Qt visualizer panels now drive bar height, pulse size, ring length, node size,
  and waveform movement from the runtime signal when available, with the old
  procedural motion retained as a fallback.
- Qt visualizer motion is locked to the live playback position so pause/resume
  and seeking do not feel like unrelated animation.
- Qt runtime refreshes preserve the current scroll position, fixing the
  Visualizer page jumping back to the top every second.

Still deferred:

- deeper GPU/OpenGL visualizer backend
- direct Qt-side FFT capture
- replacing the legacy player shell

## Phase 2AH Notes

Improved Qt shell command clarity and removed topbar dead zones:

- The topbar `RETREAT` and `ADVANCE` buttons now work as page-history back and
  forward controls.
- The profile button now reports `PROFILE LATER PHASE` instead of silently doing
  nothing.
- Connection labels now use plain legacy-player language:
  - `LEGACY CONNECTED`
  - `LEGACY STALE`
  - `LEGACY OFFLINE`
  - `START LEGACY PLAYER FOR CONTROLS`
- The action chip now shows `COMMAND SENT` immediately after Qt writes a command
  and returns to a connection-aware idle state instead of always saying `READY`.
- If Qt is opened before the legacy player, idle action labels update when the
  runtime bridge connects.

Still deferred:

- profile/account page
- full browser-like keyboard navigation
- replacing the legacy player shell

## Phase 2AI Notes

Added UIverse-inspired Qt button variants while preserving the black-and-white
cyber direction:

- `uvDragonfly`: sharp transport/history buttons inspired by
  `OnCloud125252/angry-dragonfly-77`.
- `uvPug`: high-contrast primary play/toggle buttons inspired by
  `tirth_5172/yellow-pug-84`.
- `uvSloth`: raised add/selected-mode buttons inspired by
  `zjssun/tidy-sloth-40`.
- `uvStingray`: bottom-edge resync/playlist action buttons inspired by
  `xopc333/modern-stingray-68`.
- `uvEmu`: profile/drop action buttons inspired by
  `Galahhad/ancient-emu-61`.

Implementation notes:

- Adapted the designs into Qt stylesheet object names instead of adding HTML/CSS
  or webview surfaces.
- Kept all colors monochrome; no yellow/green/purple palette drift.
- UIverse pages list elements under the MIT License.

Still deferred:

- true animated border/pseudo-element effects, which Qt stylesheets do not
  support directly
- possible custom-painted Qt button widgets if we want closer UIverse motion

## Phase 2AJ Notes

Started the Qt UI bug-sweep / honest-controls pass:

- The large Now Playing progress slider now supports seeking, matching the
  bottom player bar behavior.
- Seek attempts now report `SEEK OFFLINE` or `NO DURATION` instead of failing
  silently.
- Search page Enter now reports `SEARCH FILTERED` or `SEARCH READY`.
- Playlist cards now have explicit `VIEW` / `CREATE` actions:
  - saved playlist cards report `PLAYLIST VIEW LATER PHASE`
  - empty playlist state reports `CREATE PLAYLIST IN LEGACY`
- Source cards now have explicit `MANAGE` actions that report source-specific
  later-phase status instead of feeling inert.

Still deferred:

- real Qt playlist detail pages
- real Qt source management pages
- visual screenshot pass for button spacing across all viewport sizes

## Phase 2AK Notes

Made the Qt Playlists page more real:

- The read-only app snapshot now exposes playlist previews with:
  - playlist name
  - valid track count
  - up to three track summaries
- Qt playlist cards now show real preview rows instead of only playlist names.
- Saved playlist cards now have a real `PLAY` action when the legacy player is
  connected.
- Added the `play_playlist` runtime command to the Qt-to-legacy bridge.
- The legacy player handles `play_playlist` by building a queue from the saved
  playlist and starting the first valid track.

Still deferred:

- full Qt playlist detail pages
- Qt playlist create/delete/reorder controls
- playlist export from Qt

## Phase 2AL Notes

Made the Qt Sources page more useful without migrating source playback yet:

- Source snapshots now include detail text, action labels, and the legacy view
  key each source maps to.
- Runtime commands now allow `open_legacy_view`.
- Qt source cards now send `open_legacy_view` when the legacy player is live.
- The legacy player handles those commands by opening existing views:
  - Local Library
  - Stream / SoundCloud
  - Stream / YouTube
  - Stream / Archive
  - NetStream

Still deferred:

- executing source searches directly inside Qt
- stream-result playback from Qt cards
- full source settings and account management in Qt

## Phase 2AM Notes

Added source search handoff from Qt to the legacy player:

- The Qt Sources page now includes a Source Search Handoff panel.
- A typed query can be sent to SoundCloud, YouTube, or Archive.
- Qt still uses the existing `open_legacy_view` command, now with optional
  `query` and `search` payload fields.
- The legacy player switches to the matching stream source, fills the existing
  search variable, and calls the existing source search method.

Still deferred:

- rendering remote source results directly inside Qt
- stream-result playback from Qt result cards
- account/source settings inside Qt

## Phase 2AN Notes

Fixed Qt text input instability during live refresh:

- The state timer no longer forces a full shell rebuild every second.
- Runtime/app snapshot refreshes now defer page rebuilds while a `QLineEdit`
  has focus.
- The pending rebuild runs after the text box loses focus, so live bridge state
  can still catch up without deleting the active input field.
- Action chips still update during the deferred refresh path.

This specifically protects the top search field, Search page input, and Sources
handoff query box from resetting while typing.

## Phase 2AO Notes

Fixed the remaining Sources-page jump after pressing source buttons:

- Command acknowledgement refreshes no longer rebuild the current page.
- The Sources page stays mounted after SoundCloud, YouTube, or Archive handoff
  buttons are clicked.
- Runtime state and action-chip feedback still refresh from the command bridge.

This keeps source handoff buttons from feeling like they fling or reset the UI.

## Phase 2AP Notes

Adjusted Sources handoff button behavior:

- Clicking SoundCloud, YouTube, or Archive with an empty query now opens that
  source in the legacy player.
- Clicking those same buttons with typed text opens the source and starts the
  search.

The buttons now behave like source open/search controls instead of requiring a
query every time.

## Phase 2AQ Notes

Added read-only legacy source telemetry:

- Runtime snapshots now include `source_status`.
- The legacy player publishes active stream source, current source query,
  result count, and source status label text.
- The Qt Sources page now shows that telemetry in a dedicated panel.
- The panel updates from live runtime refreshes without rebuilding the Sources
  page while the user is typing or clicking source controls.

Still deferred:

- rendering full remote source result cards in Qt
- playing individual stream results from Qt result cards

## Phase 2AR Notes

Added read-only source result previews:

- Runtime snapshots now include normalized `source_results` rows.
- The legacy player publishes up to eight current source results from:
  - SoundCloud
  - YouTube
  - Archive
- The Qt Sources page shows the first six rows under Legacy Result Preview.

Still deferred:

- clickable Qt result cards
- direct Qt playback of remote source results
- full artwork rendering for source search result previews

## Phase 2AS Notes

Converted source result preview rows into Qt cards:

- Source results now render in a dedicated `Source Results` panel.
- The panel uses stable card slots so runtime refresh can update content without
  rebuilding the Sources page.
- Cards show source, duration, title, and artist/creator metadata.
- Empty/offline states are shown as a single card instead of loose text rows.

Still deferred:

- clickable result-card actions
- remote artwork thumbnails in source result cards
- direct playback from Qt result cards

## Phase 2AT Notes

Made source result cards actionable through the legacy command bridge:

- SoundCloud and YouTube result cards now expose a `PLAY` action.
- Archive result cards now expose a `BROWSE` action because archive search rows
  represent items that must load a file list before playback.
- The Qt shell sends `play_source_result` with the source key and result index.
- The legacy player still owns stream resolution, downloads, and playback.

Still deferred:

- remote artwork thumbnails in source result cards
- direct Qt playback of remote source results

## Phase 2AU Notes

Added artwork thumbnails to Qt source result cards:

- Source result cards now reserve a stable thumbnail slot.
- SoundCloud and YouTube result cards reuse the existing runtime `art_url`
  fields and Qt remote-cover cache.
- Archive result cards now publish Internet Archive cover URLs through
  `https://archive.org/services/img/{identifier}`.
- Remote cover fetch completion updates live widgets without rebuilding the
  whole Sources page.

Still deferred:

- direct Qt playback of remote source results

## Phase 2AV Notes

Tightened Qt shell fit inside the executable window:

- Reduced the fixed sidebar width and main content margins.
- Split the top bar into search/actions and status rows.
- Disabled horizontal scrolling in the main content area.
- Reduced wide 3-4 column layouts to two-column or stacked layouts.
- Tightened the bottom player bar so long track text can wrap instead of
  forcing the window wider.

## Phase 2AW Notes

Second responsive fit pass:

- Shortened the profile control and made status chips wrap/compress.
- Reduced fixed artwork and route-map cell widths.
- Wrapped long now-playing hero text and bridge status values.
- Changed visualizer mode buttons from one long row into a two-row grid.
- Shortened the dashboard signal-strip subtitle.

## Phase 2AX Notes

Removed white-filled Qt button states:

- Converted `uvPug`, `primaryControl`, and `uvPlay` from white-filled buttons
  to black buttons with white outlines/text.
- Removed white hover/pressed fills from the UIverse-inspired button variants.
- Kept white only as line/text/accent treatment for the monochrome cyber theme.

## Phase 2AY Notes

Removed the white page canvas behind Qt panels:

- Set the main Qt surface, scroll content, and scroll viewport backgrounds to
  black.
- Added a black default QWidget background so unnamed page wrapper widgets no
  longer fall back to Qt's light default.
- Kept labels transparent so text does not create black boxes over panels.

## Phase 2AZ Notes

Reworked scanline treatment:

- Removed the single bright moving visualizer scanline.
- Added a subtle multi-line CRT overlay inside visualizer canvases.
- Replaced the 2px white `_scanline()` divider with a small CRT band made of
  multiple uneven thin lines.
- The effect now reads as screen texture instead of a loading bar.

## Phase 2BA Notes

Animated the CRT scanline texture:

- CRT overlays now use their own animation clock, so they move even when
  playback is paused or offline.
- Reduced the overlay alpha to keep the scanlines transparent like CRT/camera
  footage.
- The small CRT divider bands now drift subtly instead of staying static.

## Phase 2BB Notes

Added interpolated button hover glow:

- Installed a global Qt button hover event filter.
- Buttons now animate a soft white drop-shadow in and out on hover.
- The glow uses easing instead of stylesheet-only instant hover changes.
- Disabled buttons fade the glow back out automatically.

## Phase 2BC Notes

Refined button hover glow timing:

- Hover-in now uses a slightly longer 280ms eased ramp.
- Hover-out now uses a slower 420ms fade with a gentler easing curve.
- The shadow effect is kept briefly after fade-out so Qt does not remove the
  glow before the animation is visible.

## Phase 2BD Notes

Added button click pulse animation:

- Button press now ramps the glow to a brighter pulse quickly.
- Button release eases the glow back to hover level if the pointer remains on
  the button.
- Button release fades the glow out if the pointer leaves during the click.
- The click pulse uses the same global event filter, so it applies to rebuilt
  page/card/source buttons automatically.

## Phase 2BE Notes

Removed hover-glow window artifact:

- Replaced `QGraphicsDropShadowEffect` button glow with an in-widget animated
  style change.
- Button glow now interpolates background, text, and border intensity directly
  on the button.
- This avoids the faint floating translucent window that could appear during
  page changes.

## Phase 2BF Notes

Added Qt-native click spark feedback:

- Button clicks now emit a short radial spark burst from the pointer position.
- The effect is implemented with a transparent Qt overlay, not React/web UI.
- Sparks use fading monochrome strokes to stay within the black-and-white cyber
  direction.
- The global button event filter triggers the effect for existing and rebuilt
  page/card/source buttons.

## Phase 2BG Notes

Made click spark feedback universal:

- Any left-click inside the Qt shell can now emit the click spark, not only
  button clicks.
- The button pulse/glow remains scoped to buttons.
- Tightened the spark radius and trail length again so the click reads smaller
  and sharper.

## Phase 2BH Notes

Added a Faulty Terminal-inspired Qt background:

- Replaced the flat black page canvas with a native animated terminal surface.
- The root background now paints monochrome glyph drift, subtle grid lines,
  transparent CRT scanlines, and horizontal glitch bands.
- Page/header/scroll wrapper surfaces are transparent so the background shows
  through the negative space.
- Panels, cards, sidebars, and controls remain dark/translucent enough to keep
  the interface readable.
- This is implemented in PySide6/Qt only; no React or webview surface was added.

## Phase 2BI Notes

Corrected Faulty Terminal visual direction:

- Replaced the terminal text-rain interpretation with a closer Qt translation
  of the ReactBits component source.
- The background now uses compact 5x5 square/digit cells instead of character
  strings.
- Added procedural cell intensity, flicker, dither/noise, moving scanline bars,
  glitch displacement bands, mouse influence, and subtle CRT curvature.
- Kept the implementation native to PySide6/Qt while matching the linked
  square-cell CRT shader much more closely.

## Phase 2BJ Notes

Optimized Faulty Terminal background performance:

- Reduced the background repaint rate from shader-like 30fps to a lighter
  terminal pulse cadence.
- Increased square-cell size to reduce per-frame cell count.
- Reduced dither density, glitch band count, scanline density, and procedural
  noise passes.
- Cached translucent black/white colors to avoid recreating QColor objects for
  thousands of tiny squares per repaint.
- Added a fast mouse-influence cutoff so distant cells skip ripple math.

## Phase 2BK Notes

Added aggressive background performance mode:

- The Faulty Terminal background now renders to a smaller cached pixmap and
  scales that frame to the window instead of repainting full-resolution cells.
- Lowered the animation cadence again so UI input stays responsive.
- Opaque panels/cards/sidebar/playerbar were restored to reduce transparent
  compositing cost while keeping the background visible in open page space.
- Mouse reactivity still feeds into the next cached frame rather than forcing
  an expensive repaint on every pointer move.

## Phase 2BL Notes

Smoothed cached Faulty Terminal animation:

- Kept expensive square-cell frame generation cached, but added a faster cheap
  repaint loop for visual blending.
- New cached frames now crossfade against the previous frame so squares fade
  out/in instead of hard-stepping.
- Raised the cached render resolution slightly to reduce blocky scaling while
  keeping rendering below full-window cost.
- The background should feel smoother without returning to full CPU shader
  simulation.

## Phase 2BM Notes

Added credit-aware component polish:

- Replaced the plain Qt volume control with a native elastic slider inspired by
  the React Bits Elastic Slider interaction.
- The volume bar now stretches on edge overflow, grows on hover, and snaps back
  with eased spring-like motion.
- Added a dedicated Contributors page to the Qt shell navigation.
- Seeded the Contributors page with the React Bits and UIVerse references that
  already influence the shell, each with a direct outbound link.
- Future borrowed interactions can be appended to one credit ledger instead of
  disappearing into commit history.

## Phase 2BN Notes

Fixed elastic volume slider availability:

- The elastic volume widget now remains draggable even when no song is playing.
- Visual volume movement no longer depends on the legacy bridge live state.
- Releasing the slider still sends the volume command only when the legacy
  player bridge is connected.

## Phase 2BO Notes

Fixed elastic slider edge clipping:

- Added reserved internal padding inside the custom volume slider so overscroll
  stretch has room to render.
- Moved the `-` and `+` markers inward enough to avoid clipping during edge
  bounce.
- Slightly widened the playerbar volume control to preserve usable track width
  while keeping the elastic stretch visible.

## Phase 2BP Notes

Added Text Type-inspired typing prompts:

- Added a Qt-native TextType placeholder animator inspired by React Bits.
- The top search bar, Search page input, and Sources query input now cycle
  through typewriter-style placeholder prompts with a blinking cursor.
- The effect only runs while the field is empty, so it never overwrites or
  fights user-entered text.
- Added React Bits Text Type to the Contributors ledger.

## Phase 2BQ Notes

Added Target Cursor mode:

- Added a toggleable Qt-native cursor overlay inspired by React Bits Target
  Cursor.
- Settings now includes an Interface Modes panel with an Enable/Disable Target
  Cursor button.
- When enabled, the default cursor is hidden, a dot follows the mouse, four
  corners spin while idle, shrink on click, and lock onto buttons, inputs, and
  sliders.
- Added React Bits Target Cursor to the Contributors ledger.

## Phase 2BR Notes

Fixed Target Cursor target alignment:

- Target-corner locking now maps widget screen/global coordinates back into the
  overlay before drawing.
- This avoids offsets caused by nested Qt layouts, sidebar/main containers, or
  window chrome coordinate differences.

## Phase 2BS Notes

Added Blur Text typing feedback:

- Added a Qt-native typed-letter blur overlay inspired by React Bits Blur Text.
- When users type into Qt text fields, newly added letters get a brief
  soft-focus echo that resolves/fades near the cursor.
- The actual input remains native and crisp, so the effect does not interfere
  with editing, selection, or search behavior.
- Added React Bits Blur Text to the Contributors ledger.

## Phase 2BT Notes

Adjusted Blur Text reveal order:

- Newly typed native glyphs are now briefly masked under the blur echo.
- The mask fades as the blur resolves, so the animated soft text appears before
  the crisp input instead of after it.
- The input contents remain unchanged; this is only a temporary visual overlay.

## Phase 2BU Notes

Added Pill Nav-inspired sidebar:

- Reworked the left tab console into a native Qt pill navigation rail inspired
  by React Bits Pill Nav.
- Active page state now uses a smooth sliding white pill indicator behind the
  current tab.
- Sidebar tab labels were simplified from bracket commands into compact
  centered pills.
- Added React Bits Pill Nav to the Contributors ledger.

## Phase 2BV Notes

Fixed Pill Nav active refresh:

- Active pill styles now refresh immediately after a page switch instead of
  waiting for the pointer to leave hover state.
- Nav buttons are raised above the sliding indicator after each move so text
  and active fill repaint cleanly.

## Phase 2BW Notes

Replaced the Pill Nav sidebar with a Magic UI Dock-inspired native Qt rail:

- Added custom DockNavButton and DockNavRail widgets instead of using a sliding
  pill indicator.
- Sidebar entries now behave like compact dock icons with cursor-distance
  magnification and immediate active-page painting.
- Kept the implementation inside PySide6 with no HTML, React, or webview code.
- Updated the Contributors ledger to credit Magic UI Dock, Build UI, and Ritesh
  Bucha for the navigation reference.

## Phase 2BX Notes

Added Cult UI Family Button-inspired source handoff tiles:

- Replaced the generic SoundCloud, YouTube, and Archive handoff buttons on the
  Sources page with native Qt expandable source tiles.
- Each tile has a monochrome custom-painted source icon so the shell keeps the
  black and white cyber direction without depending on downloaded logo files.
- Hover/focus expands the tile with extra handoff copy; clicking still sends the
  existing legacy player source search/open command.
- Added Cult UI Family Button to the Contributors ledger.

## Phase 2BY Notes

Tuned source tiles and dock motion:

- Source handoff tiles now reserve their full expansion height up front, so the
  SoundCloud tile cannot paint over nearby UI while expanding.
- Excluded custom-painted Dock and Source Family buttons from the generic button
  glow filter to prevent a second hover skin from appearing on top of them.
- Dock magnification now follows the pointer directly instead of restarting an
  easing animation on every mouse move, making the left console feel smoother.

## Phase 2BZ Notes

Fixed SoundCloud source icon bounds:

- Redrew the custom SoundCloud glyph with proportional geometry inside the tile
  icon box.
- Added a paint clip around source glyphs so icons cannot spill into the source
  label area.

## Phase 2CA Notes

Added smooth page scrolling and Scroll Reveal-inspired text:

- Replaced the main page scroll area with a SmoothScrollArea that lerps wheel
  movement into the scrollbar instead of jumping by raw wheel ticks.
- Added scroll-position reveal opacity to page headings, captions, metrics, and
  panel copy as they enter the viewport.
- Kept the player bar fixed while only the page body scrolls.
- Added React Bits Scroll Reveal to the Contributors ledger.

## Phase 2CB Notes

Stabilized smooth scroll and reveal:

- SmoothScrollArea now catches wheel events at the viewport level, so nested page
  widgets cannot bypass the lerped scroll handler.
- Replaced broad opacity reveal with blur-only reveal on headline-style labels.
- Left normal page copy visible to avoid flickery or disappearing page content.

## Phase 2CC Notes

Strengthened smooth scroll and loading blur reveal:

- SmoothScrollArea now installs an event filter and catches wheel events from
  child widgets inside the page body, not only the scroll area's viewport.
- Increased scroll interpolation duration so wheel movement feels visibly lerped.
- Scroll Reveal now triggers a loading-style blur animation from blurred to sharp
  when eligible text enters the viewport.
- Expanded reveal targets beyond page titles to include section headings, track
  titles, accent labels, muted captions, and larger mono values.
