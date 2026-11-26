"""Wrap the day's quote to a pixel width the 1080x1920 frame can actually hold.

Replaces `fold -s -w 26`, which wrapped by CHARACTER COUNT. Character count is
not width: in DejaVu Sans Bold at 64px, 26 narrow characters ("I'm still
trying to") measure about 620px while 26 wide ones ("am both happy and sad
and") measure about 1010px. One leaves half the frame empty, the other runs
off a 1080px frame. Which you get depends on the letters the day's quote
happens to contain, so the overflow arrived at random and looked intermittent.

Across the 8319-entry bank, 26 columns produced lines up to 1176px — 48px
off each edge of a 1080px frame. All-caps quotes are the worst, capitals
being much wider than lowercase. About 1 day in 213 clipped outright, and
many more rendered with only a few pixels to spare.

The second, and more visible, half is the trailing space. `fold -s` breaks
*after* the space, so every line but the last ended in one. Under the
FFmpeg 8 now on GitHub's runners that trailing space draws as a .notdef
box: the column of empty rectangles down the right-hand edge of the Shorts.
The last line, having no trailing space, was the only one without a box —
which is exactly what the broken renders showed. The box also adds its own
advance (38px at 64px, against 22px for a space), pushing marginal lines
the rest of the way off the frame.

To be clear about what did NOT change: FFmpeg 7+ shapes drawtext through
libharfbuzz, but shaping is not the culprit. Shaping these lines through
HarfBuzz 8 gives advances identical to the plain hmtx sum below, 2px
narrower where a kern pair applies — never wider. The widths were always
unbounded; FFmpeg 8 only made the failure visible.

Widths here are measured from the font file itself — TrueType `hmtx` advance
widths, looked up through `cmap`. No third-party module, so there is nothing
to install on the runner and nothing that drifts with a pip release. Kerning
and ligatures are ignored, which only makes the estimate wider than the truth:
the safe direction for a fit check.

Every emitted line is right-stripped. `fold -s` breaks *after* the space and
so left a trailing space on every line; under FFmpeg 8 that space renders as a
.notdef box, which is the column of empty rectangles that appeared down the
right-hand edge of the Shorts. The last line, having no trailing space, was
the only one without a box.

Usage:
    wrap_quote.py <quote.txt> <out.txt> <font.ttf> [max_width] [max_height]
        Wrap the quote; prints "<fontsize> <line_spacing>".
    wrap_quote.py --fit <text.txt> <font.ttf> <max_width> <max_size>
        Size a single unwrapped line (the author credit); prints "<fontsize>".

make_video.sh feeds the printed sizes to drawtext, so the shrink-to-fit
decision and the render always agree.
"""
import struct
import sys

# The frame is 1080 wide. 80px of air each side keeps the text clear of the
# edge and of the Shorts UI rail. It is also margin against the measurement
# being wrong: a line would have to render 16.5% wider than measured to reach
# the frame edge, and the HarfBuzz check above puts the real error at 0%.
DEFAULT_MAX_W = 1080 - 2 * 80

# The quote block is drawn at y=(h-text_h)/2-320 and the author line lands near
# y=1095. 800px of block keeps the two from colliding and keeps the first line
# clear of the top of the frame.
DEFAULT_MAX_H = 800

LINE_SPACING = 18
# Tried largest first; the first size whose wrap fits both bounds wins.
FONT_SIZES = (64, 60, 56, 52, 48, 44, 40)


class Font:
    """Just enough TrueType to measure a string: cmap lookup + hmtx advances."""

    def __init__(self, path):
        with open(path, "rb") as f:
            self.data = f.read()
        tables = self._tables()
        head_off = tables["head"][0]
        self.units_per_em = struct.unpack_from(">H", self.data, head_off + 18)[0]
        hhea_off = tables["hhea"][0]
        ascender, descender = struct.unpack_from(">hh", self.data, hhea_off + 4)
        num_h_metrics = struct.unpack_from(">H", self.data, hhea_off + 34)[0]
        # FreeType lays lines out on ascender-to-descender, not the point size.
        self.line_height_em = (ascender - descender) / self.units_per_em
        self.advances = self._hmtx(tables["hmtx"][0], num_h_metrics)
        self.cmap = self._cmap(tables["cmap"][0])

    def _tables(self):
        count = struct.unpack_from(">H", self.data, 4)[0]
        out = {}
        for i in range(count):
            tag, _sum, off, length = struct.unpack_from(">4sIII", self.data, 12 + 16 * i)
            out[tag.decode("latin1")] = (off, length)
        return out

    def _hmtx(self, off, num_h_metrics):
        adv = []
        for i in range(num_h_metrics):
            adv.append(struct.unpack_from(">H", self.data, off + 4 * i)[0])
        return adv

    def _cmap(self, off):
        """Prefer a format 12 (full Unicode) subtable, else format 4 (BMP)."""
        count = struct.unpack_from(">H", self.data, off + 2)[0]
        best = None
        for i in range(count):
            plat, enc, sub = struct.unpack_from(">HHI", self.data, off + 4 + 8 * i)
            fmt = struct.unpack_from(">H", self.data, off + sub)[0]
            rank = {12: 3, 4: 2}.get(fmt, 0)
            if (plat, enc) in ((3, 10), (3, 1), (0, 3), (0, 4), (0, 6)) and rank:
                if best is None or rank > best[0]:
                    best = (rank, fmt, off + sub)
        if best is None:
            raise ValueError("no usable cmap subtable")
        _, fmt, sub_off = best
        return self._cmap12(sub_off) if fmt == 12 else self._cmap4(sub_off)

    def _cmap4(self, off):
        seg_x2 = struct.unpack_from(">H", self.data, off + 6)[0]
        n = seg_x2 // 2
        ends = struct.unpack_from(f">{n}H", self.data, off + 14)
        starts_off = off + 16 + seg_x2
        starts = struct.unpack_from(f">{n}H", self.data, starts_off)
        deltas_off = starts_off + seg_x2
        deltas = struct.unpack_from(f">{n}h", self.data, deltas_off)
        ranges_off = deltas_off + seg_x2
        ranges = struct.unpack_from(f">{n}H", self.data, ranges_off)
        table = {}
        for i in range(n):
            for c in range(starts[i], min(ends[i], 0xFFFF) + 1):
                if ranges[i] == 0:
                    gid = (c + deltas[i]) & 0xFFFF
                else:
                    addr = ranges_off + 2 * i + ranges[i] + 2 * (c - starts[i])
                    if addr + 2 > len(self.data):
                        continue
                    gid = struct.unpack_from(">H", self.data, addr)[0]
                    if gid:
                        gid = (gid + deltas[i]) & 0xFFFF
                if gid:
                    table[c] = gid
        return table

    def _cmap12(self, off):
        n_groups = struct.unpack_from(">I", self.data, off + 12)[0]
        table = {}
        for i in range(n_groups):
            start, end, gid = struct.unpack_from(">III", self.data, off + 16 + 12 * i)
            if end - start > 0x10FFFF:
                continue
            for c in range(start, end + 1):
                table[c] = gid + (c - start)
        return table

    def advance(self, ch):
        gid = self.cmap.get(ord(ch), 0)
        if gid < len(self.advances):
            return self.advances[gid]
        # Glyphs past numberOfHMetrics all share the last advance.
        return self.advances[-1] if self.advances else 0

    def width(self, text, size):
        return sum(self.advance(c) for c in text) * size / self.units_per_em

    def line_height(self, size):
        return self.line_height_em * size


def split_word(font, word, size, max_w):
    """Last resort for a word too long for any line: break it on character
    boundaries. Only reached once shrinking the font has already failed."""
    parts, cur = [], ""
    for ch in word:
        if cur and font.width(cur + ch, size) > max_w:
            parts.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        parts.append(cur)
    return parts


def wrap(font, text, size, max_w, break_words=False):
    """Greedy word wrap by measured width.

    Returns None if a single word cannot fit on a line of its own, so the
    caller can try a smaller size before resorting to breaking the word —
    shrinking the quote reads better than hyphen-less mid-word breaks.
    """
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}" if cur else word
        if font.width(trial, size) <= max_w:
            cur = trial
            continue
        if font.width(word, size) > max_w:
            if not break_words:
                return None
            parts = split_word(font, word, size, max_w)
            for part in parts[:-1]:
                if cur:
                    lines.append(cur)
                    cur = ""
                lines.append(part)
            word = parts[-1]
        if cur:
            lines.append(cur)
        cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_line(argv):
    """Largest size at or below max_size that keeps a single line inside
    max_width. The author credit is not wrapped, and one bank entry
    ("Buddha Siddhartha Guatama Shakyamuni") is 985px wide of a 1080 frame at
    the fixed 44px — the same unbounded-width bug as the quote, so it gets the
    same treatment rather than waiting its turn to clip."""
    if len(argv) != 4:
        raise SystemExit("usage: wrap_quote.py --fit <text.txt> <font.ttf> "
                         "<max_width> <max_size>")
    text_path, font_path, max_w, max_size = argv
    max_w, max_size = int(max_w), int(max_size)
    with open(text_path, encoding="utf-8") as f:
        text = " ".join(f.read().split())
    font = Font(font_path)
    size = max_size
    while size > 12 and font.width(text, size) > max_w:
        size -= 2
    if size != max_size:
        print(f"author credit shrunk to {size}px to fit {max_w}px", file=sys.stderr)
    print(size)


def main():
    if sys.argv[1:2] == ["--fit"]:
        return fit_line(sys.argv[2:])
    if len(sys.argv) < 4:
        raise SystemExit("usage: wrap_quote.py <quote.txt> <out.txt> <font.ttf> "
                         "[max_width] [max_height]")
    quote_path, out_path, font_path = sys.argv[1:4]
    max_w = int(sys.argv[4]) if len(sys.argv) > 4 else DEFAULT_MAX_W
    max_h = int(sys.argv[5]) if len(sys.argv) > 5 else DEFAULT_MAX_H

    with open(quote_path, encoding="utf-8") as f:
        text = " ".join(f.read().split())
    if not text:
        raise SystemExit("quote file is empty")

    font = Font(font_path)
    chosen, lines = None, None
    for size in FONT_SIZES:
        candidate = wrap(font, text, size, max_w)
        if candidate is None:
            continue
        block_h = (len(candidate) * font.line_height(size)
                   + (len(candidate) - 1) * LINE_SPACING)
        if block_h <= max_h:
            chosen, lines = size, candidate
            break
    if chosen is None:
        # Nothing fit even at the smallest size. Break the offending word
        # rather than fail the render or let one word run off the frame, and
        # say so loudly in the run log.
        chosen = FONT_SIZES[-1]
        lines = wrap(font, text, chosen, max_w, break_words=True)
        print(f"::warning::quote does not fit at {chosen}px "
              f"({len(lines)} lines); broke a long word to fit", file=sys.stderr)

    widest = max(font.width(l, chosen) for l in lines)
    block_h = len(lines) * font.line_height(chosen) + (len(lines) - 1) * LINE_SPACING
    print(f"wrap: {len(lines)} lines @ {chosen}px — "
          f"widest {widest:.0f}px / {max_w}px, block {block_h:.0f}px / {max_h}px",
          file=sys.stderr)

    # rstrip every line: a trailing space renders as a .notdef box under
    # FFmpeg 8's harfbuzz shaping.
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(l.rstrip() for l in lines) + "\n")

    print(f"{chosen} {LINE_SPACING}")


if __name__ == "__main__":
    main()
