"""
037_fast_hover.py — Only update changed rows on hover, not all 47.

_tl_update_highlight loops through every row calling itemconfig/delete
which takes 31ms. On hover we only need to update:
1. The previously hovered row (un-highlight it)
2. The newly hovered row (highlight it)
3. The playing row (keep ▶ indicator)

Everything else stays the same.
"""
import types


def apply(app):
    from oternos.constants import C

    _prev_hover = [-1]

    def _fast_highlight(self):
        if getattr(self, '_closing', False):
            return
        try:
            if not self.track_list.winfo_exists():
                return
        except Exception:
            return
        if not hasattr(self, '_display_indices'):
            return

        RH    = self._tl_row_h
        hover = self._tl_hover_idx
        prev  = _prev_hover[0]

        def _row_bg(row, lib_idx):
            is_sel   = (lib_idx == self.current_idx)
            is_hover = (row == hover)
            if is_hover:   return C['select2']
            if is_sel:     return C['select']
            if row % 2:    return C['panel2']
            return C['bg']

        # Update previously hovered row
        if prev >= 0 and prev != hover and prev < len(self._display_indices):
            lib_idx = self._display_indices[prev]
            bg = _row_bg(prev, lib_idx)
            try:
                self.track_list.itemconfig(f'row{prev}', fill=bg)
            except Exception:
                pass

        # Update newly hovered row
        if hover >= 0 and hover < len(self._display_indices):
            lib_idx = self._display_indices[hover]
            try:
                self.track_list.itemconfig(f'row{hover}', fill=C['select2'])
            except Exception:
                pass

        # Update playing row ▶ indicator (only if it changed)
        cur = self.current_idx
        if cur in self._display_indices:
            row = self._display_indices.index(cur)
            # Only redraw play indicator if hover moved onto/off playing row
            if row == hover or row == prev:
                self.track_list.delete(f'play_ind{row}')
                if row != hover:  # only show ▶ when not hovered
                    h   = RH
                    y   = row * RH
                    W   = max(self.track_list.winfo_width(), 400)
                    self.track_list.create_text(
                        W - 50, y + h // 2,
                        text='▶', anchor='e',
                        font=('Courier New', 8),
                        fill=C['white'],
                        tags=f'play_ind{row}',
                    )

        _prev_hover[0] = hover

    app._tl_update_highlight = types.MethodType(_fast_highlight, app)
