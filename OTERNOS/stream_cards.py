"""
stream_cards.py — OTERNOS PLAYER
Shared canvas-based card list for all streaming tabs.
Replaces tk.Listbox with rich cards: thumbnail, badges, hover animation,
and a pywebview detail window on click.

Usage in any mixin:
    from .stream_cards import StreamCardList, open_detail_window

    # In _build_*_view:
    self._sc_cards = StreamCardList(
        parent_frame, self.root,
        on_play   = lambda track: ...,
        on_queue  = lambda track: ...,
        source    = "soundcloud"   # "youtube" | "deezer" | "bandcamp" | "archive"
    )

    # To populate:
    self._sc_cards.set_tracks(tracks)
"""

from __future__ import annotations
import sys, os, threading, math, time, json, tempfile, tkinter as tk
from pathlib import Path

if getattr(sys, "frozen", False):
    from oternos.utils import C, FM, FMS, FML, FMX
else:
    from .utils import C, FM, FMS, FML, FMX

# ── accent colours ────────────────────────────────────────────────────────────
_GREEN = "#2cb67d"
_YEL   = "#c8a84b"
_RED   = C["red"]
_GLOW  = "#7f5af0"

# Row geometry
_RH      = 52    # row height px
_THUMB_W = 44    # thumbnail width
_THUMB_H = 44    # thumbnail height
_PAD     = 4     # inner padding

# Source accent colours
_SOURCE_COL = {
    "soundcloud": "#ff5500",
    "youtube":    "#cc0000",
    "deezer":     "#a040c0",
    "bandcamp":   "#1da0c3",
    "archive":    "#428bca",
}

# ── pywebview availability check ─────────────────────────────────────────────
try:
    import webview as _webview
    _WEBVIEW_OK = True
except ImportError:
    _WEBVIEW_OK = False


# ─────────────────────────────────────────────────────────────────────────────
#  Track data normaliser — maps each source's dict to a common schema
# ─────────────────────────────────────────────────────────────────────────────
def normalise(track: dict, source: str) -> dict:
    """Return a flat dict with consistent keys regardless of source."""
    t = track
    if source == "soundcloud":
        dur_ms  = t.get("duration", 0)
        dur_s   = dur_ms // 1000 if dur_ms > 1000 else dur_ms
        return {
            "title":   (t.get("title") or "")[:80],
            "artist":  (t.get("user") or {}).get("username", ""),
            "duration": dur_s,
            "plays":   t.get("playback_count") or 0,
            "likes":   t.get("likes_count") or t.get("favoritings_count") or 0,
            "genre":   (t.get("genre") or "")[:18],
            "art_url": (t.get("artwork_url") or
                        (t.get("user") or {}).get("avatar_url") or ""),
            "url":     t.get("permalink_url") or "",
            "desc":    (t.get("description") or "")[:200],
            "_raw":    t,
        }
    elif source == "youtube":
        dur = int(t.get("duration") or 0)
        return {
            "title":   (t.get("title") or "")[:80],
            "artist":  (t.get("channel") or "")[:40],
            "duration": dur,
            "plays":   t.get("view_count") or 0,
            "likes":   0,
            "genre":   "",
            "art_url": t.get("thumbnail") or t.get("thumb") or "",
            "url":     f"https://youtube.com/watch?v={t.get('id','')}" if t.get("id") else "",
            "desc":    (t.get("description") or "")[:200],
            "_raw":    t,
        }
    elif source == "deezer":
        return {
            "title":   (t.get("title") or t.get("title_short") or "")[:80],
            "artist":  ((t.get("artist") or {}).get("name") or t.get("artist_name") or ""),
            "duration": t.get("duration", 30),
            "plays":   0,
            "likes":   0,
            "genre":   "",
            "art_url": (t.get("album") or {}).get("cover_medium") or "",
            "url":     t.get("link") or "",
            "desc":    "",
            "_raw":    t,
        }
    elif source == "bandcamp":
        return {
            "title":   (t.get("title") or "")[:80],
            "artist":  (t.get("artist") or "")[:40],
            "duration": 0,
            "plays":   0,
            "likes":   0,
            "genre":   "",
            "art_url": t.get("art") or t.get("artwork") or "",
            "url":     t.get("url") or "",
            "desc":    "",
            "_raw":    t,
        }
    elif source == "archive":
        creator = t.get("creator", "")
        if isinstance(creator, list):
            creator = creator[0] if creator else ""
        return {
            "title":   (t.get("title") or t.get("identifier") or "")[:80],
            "artist":  creator[:40],
            "duration": 0,
            "plays":   0,
            "likes":   0,
            "genre":   (t.get("mediatype") or "audio")[:18],
            "art_url": "",
            "url":     f"https://archive.org/details/{t.get('identifier','')}" if t.get("identifier") else "",
            "desc":    (t.get("description") or "")[:200],
            "_raw":    t,
        }
    return {"title": str(t), "artist": "", "duration": 0, "plays": 0,
            "likes": 0, "genre": "", "art_url": "", "url": "", "desc": "", "_raw": t}


def _fmt_plays(n: int) -> str:
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000:     return f"{n//1000}k"
    return str(n) if n else ""


def _fmt_dur(s: int) -> str:
    if not s: return ""
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    if h: return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


# ─────────────────────────────────────────────────────────────────────────────
#  StreamCardList — the main canvas widget
# ─────────────────────────────────────────────────────────────────────────────
class StreamCardList:
    """
    Drop-in canvas-based replacement for tk.Listbox in streaming tabs.
    Draws rich cards with thumbnail, badges, hover animation.
    """

    def __init__(self, parent: tk.Frame, root: tk.Tk,
                 on_play=None, on_queue=None, on_detail=None,
                 source: str = "soundcloud"):
        self.root      = root
        self.source    = source
        self.on_play   = on_play
        self.on_queue  = on_queue
        self.on_detail = on_detail

        self._tracks:      list[dict] = []   # raw
        self._norm:        list[dict] = []   # normalised
        self._thumb_cache: dict[int, object] = {}
        self._selected     = -1
        self._hovered      = -1
        self._hover_anim   = 0.0    # 0→1 ease-in value
        self._hover_job    = None
        self._playing_id   = None
        self._width        = 400
        self._thumb_tip    = None   # small hover tooltip window

        # outer frame
        self.frame = tk.Frame(parent, bg=C["bg"])
        self.frame.pack(fill="both", expand=True)

        sb = tk.Scrollbar(self.frame, bg=C["panel"], troughcolor=C["bg"],
                          width=6, relief="flat", bd=0)
        sb.pack(side="right", fill="y")

        self.cv = tk.Canvas(self.frame, bg=C["bg"], highlightthickness=0,
                            yscrollcommand=sb.set)
        self.cv.pack(side="left", fill="both", expand=True)
        sb.config(command=self.cv.yview)

        self.cv.bind("<Configure>",    self._on_resize)
        self.cv.bind("<MouseWheel>",   self._on_scroll)
        self.cv.bind("<Motion>",       self._on_motion)
        self.cv.bind("<Leave>",        self._on_leave)
        self.cv.bind("<Button-1>",     self._on_click)
        self.cv.bind("<Double-Button-1>", self._on_dbl)
        self.cv.bind("<Button-3>",     self._on_rclick)

    # ── public API ───────────────────────────────────────────────────────────

    def set_tracks(self, tracks: list[dict], playing_id=None):
        self._tracks      = tracks
        self._norm        = [normalise(t, self.source) for t in tracks]
        self._thumb_cache = {}
        self._selected    = -1
        self._hovered     = -1
        self._playing_id  = playing_id
        self._render()
        # Kick off thumbnail fetches
        for i, n in enumerate(self._norm):
            url = n.get("art_url", "")
            if url:
                threading.Thread(target=self._fetch_thumb,
                                 args=(i, url), daemon=True).start()

    def set_playing(self, track_id):
        self._playing_id = track_id
        self._render()

    def clear(self):
        self._tracks = []
        self._norm   = []
        self._thumb_cache = {}
        self._selected = self._hovered = -1
        self.cv.delete("all")
        self.cv.configure(scrollregion=(0, 0, 100, 40))

    def show_message(self, msg: str):
        self.clear()
        self.cv.create_text(20, 20, text=msg, anchor="nw",
                            font=FM, fill=C["white3"])

    # ── rendering ────────────────────────────────────────────────────────────

    def _render(self):
        cv = self.cv
        cv.delete("all")
        if not self._norm:
            cv.create_text(20, 24, text="No results.", anchor="nw",
                           font=FM, fill=C["white3"])
            cv.configure(scrollregion=(0, 0, self._width, 48))
            return
        W = self._width
        total_h = _RH * len(self._norm)
        cv.configure(scrollregion=(0, 0, W, total_h))
        for i, n in enumerate(self._norm):
            self._draw_row(i, n, W)

    def _draw_row(self, i: int, n: dict, W: int):
        cv  = self.cv
        y0  = i * _RH
        y1  = y0 + _RH
        tag = f"row{i}"
        cv.delete(tag)

        # Background
        is_playing = (n["_raw"].get("id") == self._playing_id or
                      n["_raw"].get("video_id") == self._playing_id)
        is_hover   = i == self._hovered
        is_sel     = i == self._selected

        if is_playing:
            bg = "#0e1a0e"
        elif is_sel:
            bg = C["select2"]
        elif is_hover:
            # Ease-blended highlight
            t  = self._hover_anim
            bg = self._lerp_col(C["panel2"] if i%2==0 else C["bg"], "#2a2a3e", t)
        else:
            bg = C["panel2"] if i % 2 == 0 else C["bg"]

        cv.create_rectangle(0, y0, W, y1, fill=bg, outline="", tags=tag)

        # Left accent bar for playing track
        if is_playing:
            col = _SOURCE_COL.get(self.source, _GREEN)
            cv.create_rectangle(0, y0, 3, y1, fill=col, outline="", tags=tag)

        # Hover left bar
        if is_hover and self._hover_anim > 0.05:
            alpha_h = int(self._hover_anim * 255)
            shade   = f"#{alpha_h:02x}{alpha_h:02x}{alpha_h:02x}"
            cv.create_rectangle(0, y0, 3, y1, fill=shade, outline="", tags=tag)

        # Thumbnail area
        tx0, ty0 = _PAD, y0 + _PAD
        tx1, ty1 = tx0 + _THUMB_W, ty0 + _THUMB_H
        cv.create_rectangle(tx0, ty0, tx1, ty1,
                            fill=C["panel"], outline=C["border"], tags=tag)

        if i in self._thumb_cache:
            cv.create_image(tx0, ty0, image=self._thumb_cache[i],
                            anchor="nw", tags=tag)
        else:
            # Placeholder glyph
            glyph = {"soundcloud":"◈","youtube":"▶","deezer":"◎",
                     "bandcamp":"⊕","archive":"◉"}.get(self.source, "▶")
            col   = _SOURCE_COL.get(self.source, C["white3"])
            cv.create_text(tx0 + _THUMB_W//2, ty0 + _THUMB_H//2,
                           text=glyph, font=("Courier New", 14),
                           fill=col, anchor="center", tags=tag)

        # Play indicator overlay on thumbnail
        if is_playing:
            cv.create_rectangle(tx0, ty0, tx1, ty1,
                                fill="#000000", stipple="gray50",
                                outline="", tags=tag)
            cv.create_text(tx0 + _THUMB_W//2, ty0 + _THUMB_H//2,
                           text="▶", font=("Courier New", 16, "bold"),
                           fill=_SOURCE_COL.get(self.source, _GREEN),
                           anchor="center", tags=tag)

        # Text column
        tx = tx1 + 10
        title_col = (_SOURCE_COL.get(self.source, _GREEN)
                     if is_playing else C["white"])

        # Title
        max_title_w = W - tx - 120
        title = n["title"]
        cv.create_text(tx, y0 + 14, text=title,
                       font=("Courier New", 9, "bold"),
                       fill=title_col, anchor="w",
                       width=max_title_w, tags=tag)

        # Artist
        cv.create_text(tx, y0 + 30, text=n["artist"],
                       font=("Courier New", 8),
                       fill=C["white3"], anchor="w",
                       width=max_title_w, tags=tag)

        # Badges row
        bx = tx
        by = y0 + 46
        badges = []
        if n["duration"]: badges.append(("⏱ " + _fmt_dur(n["duration"]),  C["white3"]))
        if n["plays"]:    badges.append(("▸ " + _fmt_plays(n["plays"]),   C["white3"]))
        if n["likes"]:    badges.append(("♥ " + _fmt_plays(n["likes"]),   _RED))
        if n["genre"]:    badges.append((n["genre"],                        _GLOW))

        for text, col in badges[:4]:
            tw = len(text) * 5 + 10
            cv.create_rectangle(bx, by - 7, bx + tw, by + 7,
                                 fill=C["panel2"], outline=C["border"],
                                 tags=tag)
            cv.create_text(bx + tw//2, by, text=text,
                           font=("Courier New", 7),
                           fill=col, anchor="center", tags=tag)
            bx += tw + 4

        # Duration / right side meta
        right_x = W - 8
        dur_str = _fmt_dur(n["duration"])
        if dur_str:
            cv.create_text(right_x, y0 + _RH//2 - 8,
                           text=dur_str, font=FMS,
                           fill=C["white3"], anchor="e", tags=tag)

        # ⋯ detail button
        cv.create_text(right_x, y0 + _RH//2 + 8,
                       text="⋯", font=("Courier New", 12),
                       fill=C["white3"] if not is_hover else C["white"],
                       anchor="e", tags=tag)

        # Divider
        cv.create_line(0, y1-1, W, y1-1, fill=C["border"], tags=tag)

    # ── hover animation ──────────────────────────────────────────────────────

    def _hover_tick(self, target_idx: int):
        if self._hovered != target_idx:
            return
        self._hover_anim = min(1.0, self._hover_anim + 0.18)
        if self._norm and 0 <= target_idx < len(self._norm):
            self._draw_row(target_idx, self._norm[target_idx], self._width)
        if self._hover_anim < 1.0:
            self._hover_job = self.root.after(
                16, lambda: self._hover_tick(target_idx))
        else:
            self._hover_job = None

    def _cancel_hover_anim(self):
        if self._hover_job:
            try: self.root.after_cancel(self._hover_job)
            except Exception: pass
            self._hover_job = None

    # ── thumbnail fetching ───────────────────────────────────────────────────

    def _fetch_thumb(self, idx: int, url: str):
        if not url:
            return
        try:
            import urllib.request as _ur, io
            hq = (url.replace("-large", "-t300x300")
                     .replace("-small", "-t300x300"))
            data = _ur.urlopen(hq, timeout=5).read()
            self.root.after(0, lambda i=idx, d=data: self._load_thumb(i, d))
        except Exception:
            pass

    def _load_thumb(self, idx: int, data: bytes):
        try:
            from PIL import Image, ImageTk
            import io
            img   = Image.open(io.BytesIO(data)).resize(
                        (_THUMB_W, _THUMB_H), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
        except Exception:
            try:
                import tempfile, tkinter as _tk
                fd, tmp = tempfile.mkstemp()
                os.close(fd)
                with open(tmp, "wb") as f: f.write(data)
                photo = _tk.PhotoImage(file=tmp)
                os.unlink(tmp)
            except Exception:
                return
        self._thumb_cache[idx] = photo
        if self._norm and 0 <= idx < len(self._norm):
            self._draw_row(idx, self._norm[idx], self._width)

    # ── events ───────────────────────────────────────────────────────────────

    def _row_at(self, y_canvas: int) -> int:
        vy = self.cv.canvasy(y_canvas)
        return int(vy // _RH)

    def _on_resize(self, e):
        self._width = e.width
        self._render()

    def _on_scroll(self, e):
        self.cv.yview_scroll(int(-1 * (e.delta / 120)) * 3, "units")

    def _on_motion(self, e):
        idx = self._row_at(e.y)
        # Always reposition the tooltip — this makes it follow the cursor within a row
        if idx == self._hovered:
            self._reposition_thumb_tip(e)
            return
        # Row changed — restore old, start new hover
        old = self._hovered
        self._hovered    = -1
        self._cancel_hover_anim()
        if self._norm and 0 <= old < len(self._norm):
            self._draw_row(old, self._norm[old], self._width)
        if self._norm and 0 <= idx < len(self._norm):
            self._hovered    = idx
            self._hover_anim = 0.0
            self._hover_tick(idx)
            self._show_thumb_tip(idx, e)
        else:
            self._hide_thumb_tip()

    def _reposition_thumb_tip(self, e):
        """Move the existing tooltip to follow the cursor."""
        tip = getattr(self, "_thumb_tip", None)
        if not tip:
            return
        try:
            if not tip.winfo_exists():
                return
            SZ = 80
            sw = tip.winfo_screenwidth()
            sh = tip.winfo_screenheight()
            x  = e.x_root + 20
            y  = e.y_root - SZ // 2
            if x + SZ + 4 > sw:
                x = e.x_root - SZ - 20
            y = max(4, min(y, sh - SZ - 4))
            tip.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def _on_leave(self, e):
        self._hide_thumb_tip()
        old = self._hovered
        self._hovered = -1
        self._cancel_hover_anim()
        if self._norm and 0 <= old < len(self._norm):
            self._hover_anim = 0.0
            self._draw_row(old, self._norm[old], self._width)

    def _on_click(self, e):
        idx = self._row_at(e.y)
        if not self._norm or idx < 0 or idx >= len(self._norm):
            return
        # Check if click was on ⋯ button (rightmost 28px)
        if e.x >= self._width - 28:
            self._open_detail(idx)
            return
        self._selected = idx
        self._render()
        if self.on_play:
            self.on_play(self._tracks[idx])

    def _on_dbl(self, e):
        idx = self._row_at(e.y)
        if self._norm and 0 <= idx < len(self._norm):
            if self.on_play:
                self.on_play(self._tracks[idx])

    def _on_rclick(self, e):
        idx = self._row_at(e.y)
        if self._norm and 0 <= idx < len(self._norm):
            self._selected = idx
            if self.on_detail:
                self.on_detail(self._tracks[idx], e.x_root, e.y_root)

    # ── thumbnail tooltip ────────────────────────────────────────────────────

    def _show_thumb_tip(self, idx: int, event):
        self._hide_thumb_tip()
        n = self._norm[idx]
        art_url = n.get("art_url", "")
        if not art_url:
            return
        SZ  = 80
        tip = tk.Toplevel(self.root)
        tip.overrideredirect(True)
        tip.attributes("-topmost", True)
        tip.configure(bg=C["border"])
        self._thumb_tip = tip
        cv2 = tk.Canvas(tip, width=SZ, height=SZ,
                        bg=C["panel"], highlightthickness=0)
        cv2.pack(padx=1, pady=1)
        cv2.create_text(SZ//2, SZ//2, text="…",
                        font=("Courier New", 14), fill=C["white3"])
        try:
            sw = tip.winfo_screenwidth()
            sh = tip.winfo_screenheight()
            x  = event.x_root + 20
            y  = event.y_root - SZ // 2
            if x + SZ + 4 > sw:
                x = event.x_root - SZ - 20
            y = max(4, min(y, sh - SZ - 4))
            tip.geometry(f"+{x}+{y}")
        except Exception:
            pass
        # If already cached use it immediately
        if idx in self._thumb_cache:
            try:
                cv2.delete("all")
                cv2.create_image(0, 0, anchor="nw", image=self._thumb_cache[idx])
                cv2._photo = self._thumb_cache[idx]
            except Exception:
                pass
            return
        hq = (art_url.replace("-large", "-t300x300")
                     .replace("-small", "-t300x300"))
        def _fetch(url=hq, c=cv2, sz=SZ, t=tip):
            try:
                import urllib.request as _ur, io
                data = _ur.urlopen(url, timeout=4).read()
                from PIL import Image, ImageTk
                img   = Image.open(io.BytesIO(data)).resize((sz,sz), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                def _show(p=photo):
                    try:
                        if not t.winfo_exists(): return
                        c.delete("all")
                        c.create_image(0, 0, anchor="nw", image=p)
                        c._photo = p
                    except Exception: pass
                self.root.after(0, _show)
            except Exception:
                pass
        threading.Thread(target=_fetch, daemon=True).start()

    def _hide_thumb_tip(self):
        tip = getattr(self, "_thumb_tip", None)
        if tip:
            try: tip.destroy()
            except Exception: pass
        self._thumb_tip = None

    # ── pywebview detail window ───────────────────────────────────────────────

    def _open_detail(self, idx: int):
        n = self._norm[idx]
        if _WEBVIEW_OK:
            threading.Thread(
                target=_open_webview_detail,
                args=(n, self.source),
                daemon=True
            ).start()
        else:
            # Fallback: tkinter detail window
            _open_tk_detail(self.root, n, self.source,
                            on_play=lambda: self.on_play and self.on_play(self._tracks[idx]),
                            on_queue=lambda: self.on_queue and self.on_queue(self._tracks[idx]))

    # ── colour helper ─────────────────────────────────────────────────────────

    @staticmethod
    def _lerp_col(c1: str, c2: str, t: float) -> str:
        def h(c): return tuple(int(c.lstrip("#")[i:i+2],16) for i in (0,2,4))
        r1,g1,b1 = h(c1); r2,g2,b2 = h(c2)
        r = int(r1 + (r2-r1)*t)
        g = int(g1 + (g2-g1)*t)
        b = int(b1 + (b2-b1)*t)
        return f"#{r:02x}{g:02x}{b:02x}"


# ─────────────────────────────────────────────────────────────────────────────
#  pywebview detail window
# ─────────────────────────────────────────────────────────────────────────────
def _build_detail_html(n: dict, source: str) -> str:
    acc     = _SOURCE_COL.get(source, "#7f5af0")
    art_url = n.get("art_url", "")
    art_tag = (f'<img src="{art_url}" class="art" onerror="this.style.display=\'none\'">'
               if art_url else '<div class="art art-placeholder"></div>')
    plays_str = _fmt_plays(n["plays"]) if n["plays"] else "—"
    likes_str = _fmt_plays(n["likes"]) if n["likes"] else "—"
    dur_str   = _fmt_dur(n["duration"]) if n["duration"] else "—"
    genre     = n.get("genre") or "—"
    url       = n.get("url") or ""
    desc      = (n.get("desc") or "").replace("<","&lt;").replace(">","&gt;")
    src_label = source.upper()
    open_btn  = (f'<a href="{url}" class="open-btn" target="_blank">'
                 f'Open on {src_label} ↗</a>' if url else "")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{n['title']}</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #050505; color: #e0e0f0;
    font-family: 'Courier New', monospace;
    min-height: 100vh; padding: 32px;
  }}
  .card {{
    background: #0f0f18; border: 1px solid #1e1e2e;
    border-radius: 10px; overflow: hidden;
    max-width: 680px; margin: 0 auto;
  }}
  .top {{
    display: flex; gap: 24px; padding: 28px;
    border-bottom: 1px solid #1e1e2e;
  }}
  .art {{
    width: 160px; height: 160px; border-radius: 8px;
    object-fit: cover; flex-shrink: 0;
    background: #1e1e2e;
  }}
  .art-placeholder {{
    width: 160px; height: 160px; border-radius: 8px;
    background: linear-gradient(135deg, #1e1e2e 0%, #0f0f18 100%);
    display: flex; align-items: center; justify-content: center;
  }}
  .info {{ flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 8px; }}
  .source-badge {{
    display: inline-block; font-size: 10px; font-weight: 700;
    letter-spacing: 0.1em; padding: 3px 9px; border-radius: 4px;
    background: {acc}22; color: {acc}; border: 1px solid {acc}44;
    align-self: flex-start;
  }}
  h1 {{ font-size: 18px; font-weight: 700; color: #ffffff; line-height: 1.3; }}
  .artist {{ font-size: 13px; color: #9090a8; }}
  .stats {{
    display: flex; gap: 16px; flex-wrap: wrap; margin-top: 4px;
  }}
  .stat {{ font-size: 12px; color: #505068; }}
  .stat span {{ color: #e0e0f0; margin-left: 4px; }}
  .genre-pill {{
    display: inline-block; font-size: 11px; padding: 3px 10px;
    border-radius: 99px; background: #1e1e2e; color: {acc};
    border: 1px solid #2e2e4e; margin-top: 4px;
  }}
  .open-btn {{
    display: inline-block; margin-top: 8px; padding: 7px 18px;
    background: {acc}; color: #ffffff; border-radius: 6px;
    text-decoration: none; font-size: 12px; font-weight: 700;
    letter-spacing: 0.05em;
  }}
  .open-btn:hover {{ opacity: 0.85; }}
  .desc-section {{ padding: 20px 28px; }}
  .desc-label {{ font-size: 10px; letter-spacing: 0.1em; color: #505068;
                 margin-bottom: 8px; }}
  .desc {{ font-size: 12px; color: #9090a8; line-height: 1.7;
           white-space: pre-wrap; }}
  .accent-bar {{ height: 3px; background: {acc}; }}
</style>
</head>
<body>
<div class="card">
  <div class="accent-bar"></div>
  <div class="top">
    {art_tag}
    <div class="info">
      <span class="source-badge">{src_label}</span>
      <h1>{n['title']}</h1>
      <div class="artist">{n['artist']}</div>
      <div class="stats">
        <div class="stat">DURATION<span>{dur_str}</span></div>
        <div class="stat">PLAYS<span>{plays_str}</span></div>
        <div class="stat">LIKES<span>{likes_str}</span></div>
      </div>
      {"<span class='genre-pill'>" + genre + "</span>" if genre != "—" else ""}
      {open_btn}
    </div>
  </div>
  {"<div class='desc-section'><div class='desc-label'>DESCRIPTION</div><div class='desc'>" + desc + "</div></div>" if desc else ""}
</div>
</body>
</html>"""


def _open_webview_detail(n: dict, source: str):
    """Open track detail in a pywebview window (runs in its own thread)."""
    try:
        html = _build_detail_html(n, source)
        title = f"{n['title'][:40]}  —  {source.upper()}"
        win = _webview.create_window(title, html=html,
                                     width=720, height=520,
                                     background_color="#050505")
        _webview.start()
    except Exception:
        pass


def _open_tk_detail(root, n: dict, source: str,
                    on_play=None, on_queue=None):
    """Fallback tkinter detail window when pywebview is not installed."""
    acc = _SOURCE_COL.get(source, _GLOW)
    win = tk.Toplevel(root)
    win.title(f"{n['title'][:50]}  —  {source.upper()}")
    win.configure(bg=C["bg"])
    win.geometry("600x420")
    try:
        import ctypes
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            win.winfo_id(), 20, ctypes.byref(ctypes.c_int(1)), 4)
    except Exception:
        pass

    # Accent bar
    tk.Frame(win, bg=acc, height=3).pack(fill="x")

    body = tk.Frame(win, bg=C["bg"])
    body.pack(fill="both", expand=True, padx=24, pady=20)

    # Art + info row
    top = tk.Frame(body, bg=C["bg"])
    top.pack(fill="x", pady=(0, 16))

    art_cv = tk.Canvas(top, width=120, height=120, bg=C["panel"],
                       highlightthickness=1, highlightbackground=C["border"])
    art_cv.pack(side="left", padx=(0, 20))
    art_cv.create_text(60, 60, text="◈", font=("Courier New", 28),
                       fill=acc)

    info = tk.Frame(top, bg=C["bg"])
    info.pack(side="left", fill="both", expand=True)

    src_lbl = tk.Label(info, text=source.upper(), font=("Courier New", 8, "bold"),
                       fg=acc, bg=C["bg"])
    src_lbl.pack(anchor="w")

    tk.Label(info, text=n["title"], font=("Courier New", 11, "bold"),
             fg=C["white"], bg=C["bg"], wraplength=360, justify="left"
             ).pack(anchor="w", pady=(4, 2))

    tk.Label(info, text=n["artist"], font=FMS,
             fg=C["white3"], bg=C["bg"]).pack(anchor="w")

    stats_row = tk.Frame(info, bg=C["bg"])
    stats_row.pack(anchor="w", pady=(8, 0))
    for label, val in [("⏱", _fmt_dur(n["duration"])),
                       ("▸",  _fmt_plays(n["plays"])),
                       ("♥",  _fmt_plays(n["likes"])),
                       ("◈",  n["genre"] or "")]:
        if val:
            tk.Label(stats_row, text=f"{label} {val}", font=FMS,
                     fg=C["white2"], bg=C["bg"], padx=8
                     ).pack(side="left")

    # Desc
    if n.get("desc"):
        tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=(0, 10))
        tk.Label(body, text=(n["desc"][:300] + "…" if len(n["desc"]) > 300 else n["desc"]),
                 font=("Courier New", 8), fg=C["white3"], bg=C["bg"],
                 wraplength=540, justify="left", anchor="w"
                 ).pack(anchor="w")

    # Buttons
    tk.Frame(body, bg=C["border"], height=1).pack(fill="x", pady=(12, 8))
    btns = tk.Frame(body, bg=C["bg"])
    btns.pack(anchor="w")

    def _mk_btn(parent, text, cmd, accent=False):
        fg = C["bg"] if accent else C["white2"]
        bg = acc     if accent else C["panel2"]
        b  = tk.Label(parent, text=text, font=FM, fg=fg, bg=bg,
                      padx=12, pady=5, cursor="hand2")
        b.pack(side="left", padx=(0, 8))
        b.bind("<Button-1>", lambda e: (cmd(), win.destroy()))
        b.bind("<Enter>", lambda e: b.config(bg=C["select2"] if not accent else acc))
        b.bind("<Leave>", lambda e: b.config(bg=bg))
        return b

    if on_play:  _mk_btn(btns, "▶  PLAY",         on_play,  accent=True)
    if on_queue: _mk_btn(btns, "⊕  ADD TO QUEUE", on_queue, accent=False)

    # Try to load art
    art_url = n.get("art_url", "")
    if art_url:
        def _load_art(url=art_url, c=art_cv):
            try:
                import urllib.request as _ur, io
                hq = url.replace("-large","-t300x300").replace("-small","-t300x300")
                data = _ur.urlopen(hq, timeout=5).read()
                from PIL import Image, ImageTk
                img   = Image.open(io.BytesIO(data)).resize((120,120), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                def _show(p=photo):
                    try:
                        c.delete("all")
                        c.create_image(0, 0, anchor="nw", image=p)
                        c._photo = p
                    except Exception: pass
                root.after(0, _show)
            except Exception:
                pass
        threading.Thread(target=_load_art, daemon=True).start()
