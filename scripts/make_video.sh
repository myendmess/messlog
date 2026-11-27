#!/usr/bin/env bash
# Render a 1080x1920 vertical "Short" from the daily quote.
# Inputs (in the working directory): quote.txt, author.txt (raw text) — override
#   with QUOTE_FILE / AUTHOR_FILE for localized renders.
# Background: a random *.mp4 from assets/backgrounds/ (falls back to a solid color).
#   Everything fills the full 9:16 frame by default (BG_FIT=crop, cover-crop) —
#   full-bleed scenery is the native Shorts look. Source PORTRAIT footage
#   (1080x1920+) for zero crop loss; landscape clips show their center slice.
#   BG_FIT=blur (letterbox over blurred self) and BG_FIT=pan (slow pan across
#   a landscape clip) remain available for experiments.
# Text: bold white quote with a dark halo (max contrast on ANY footage — a
#   design-review lesson: decorative fonts and hue-tinted fills collide with
#   randomly-colored backgrounds), author in brand gold below. The quote block
#   sits in the upper half so the scenery stays visible at a light 25% darken.
# Music:      a random *.mp3 from assets/music/       (falls back to silence).
# Output: out.mp4 (override with OUT_FILE).
set -euo pipefail

# Overrides used by the localization pipeline and local testing.
QUOTE_FILE="${QUOTE_FILE:-quote.txt}"
AUTHOR_FILE="${AUTHOR_FILE:-author.txt}"
OUT_FILE="${OUT_FILE:-out.mp4}"
BG_FIT="${BG_FIT:-crop}"
FONT_BOLD="${FONT_BOLD:-/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf}"
FONT_REG="${FONT_REG:-/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf}"

case "$BG_FIT" in
  blur|pan|crop) ;;
  *) echo "BG_FIT must be one of: blur, pan, crop (got '$BG_FIT')" >&2; exit 1 ;;
esac
if [ ! -f "$QUOTE_FILE" ] || [ ! -f "$AUTHOR_FILE" ]; then
  echo "Missing input text: $QUOTE_FILE / $AUTHOR_FILE" >&2; exit 1
fi

# ffmpeg is preinstalled on GitHub-hosted ubuntu runners; install if missing.
if ! command -v ffmpeg >/dev/null 2>&1; then
  sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg
fi

# drawtext does not auto-wrap. Wrap to a width measured from the font file
# itself — see scripts/wrap_quote.py for why the old `fold -s -w 26` character
# wrap put text off both edges of the frame and a box at the end of every line.
# The wrapper also picks the font size, so a long quote shrinks instead of
# overflowing; it prints "<fontsize> <line_spacing>".
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WRAP=$(python3 "$SCRIPT_DIR/wrap_quote.py" "$QUOTE_FILE" quote_wrapped.txt "$FONT_BOLD") || WRAP=""
QUOTE_SIZE="${WRAP%% *}"; QUOTE_SPACING="${WRAP##* }"
case "${QUOTE_SIZE}:${QUOTE_SPACING}" in
  *[!0-9:]*|:*|*:) WRAP="" ;;   # non-numeric or empty -> fall back below
esac
if [ -z "$WRAP" ]; then
  # Never lose the daily Short to a wrapper problem. 22 columns rather than the
  # old 26 so even wide characters stay inside the frame, and strip the trailing
  # space `fold -s` leaves on every line — FFmpeg 8 draws that as a .notdef box.
  echo "::warning::wrap_quote.py failed — falling back to a fixed-width wrap." >&2
  fold -s -w 22 "$QUOTE_FILE" | sed 's/[[:space:]]*$//' > quote_wrapped.txt
  QUOTE_SIZE=64; QUOTE_SPACING=18
  # Same per-line layout the wrapper would have produced, without the font
  # metrics: let drawtext centre each line itself, and space them by the
  # nominal line height. Ragged-centred rather than a left-aligned block, but
  # it publishes and it carries no newlines.
  rm -f quote_wrapped_[0-9][0-9][0-9].txt
  : > quote_wrapped_layout.txt
  N=$(wc -l < quote_wrapped.txt); [ -s quote_wrapped.txt ] && N=$((N + 1))
  PITCH=$(( QUOTE_SIZE * 117 / 100 + QUOTE_SPACING ))
  TOP=$(( (1920 - (N * PITCH - QUOTE_SPACING)) / 2 - 320 ))
  I=0
  while IFS= read -r LINE || [ -n "$LINE" ]; do
    printf '%s' "$LINE" > "$(printf 'quote_wrapped_%03d.txt' "$I")"
    printf '(w-text_w)/2 %d %s\n' "$((TOP + I * PITCH))" \
      "$(printf 'quote_wrapped_%03d.txt' "$I")" >> quote_wrapped_layout.txt
    I=$((I + 1))
  done < quote_wrapped.txt
fi

printf '— %s' "$(cat "$AUTHOR_FILE")" > author_line.txt
AUTHOR_SIZE=$(python3 "$SCRIPT_DIR/wrap_quote.py" --fit author_line.txt "$FONT_REG" 920 44) || AUTHOR_SIZE=44
case "$AUTHOR_SIZE" in ''|*[!0-9]*) AUTHOR_SIZE=44 ;; esac

DUR=15
echo "Quote font: $FONT_BOLD (${QUOTE_SIZE}px), author ${AUTHOR_SIZE}px"

# White + dark halo reads on any background; quote block lifted above center
# so the lower half of the frame shows the scenery; author in brand gold.
# One drawtext layer per line, positioned by quote_wrapped_layout.txt.
# A multi-line textfile would be simpler, but FFmpeg 8's drawtext passes the
# newline ending every non-final line to HarfBuzz, which shapes it as a
# .notdef box — the rectangles that appeared at the end of each line in the
# published Shorts (FFmpeg #21565, fixed upstream in b91ac0b1ce, not yet in
# the runners' 8.0.x). Drawing line by line keeps newlines out of the filter.
QUOTE_LAYERS=""
while read -r LX LY LFILE; do
  [ -n "$LFILE" ] || continue
  QUOTE_LAYERS="${QUOTE_LAYERS:+${QUOTE_LAYERS},}drawtext=fontfile=${FONT_BOLD}:textfile=${LFILE}:fontcolor=white:borderw=4:bordercolor=black@0.85:fontsize=${QUOTE_SIZE}:x=${LX}:y=${LY}"
done < quote_wrapped_layout.txt
if [ -z "$QUOTE_LAYERS" ]; then
  echo "::error::no quote layout produced — refusing to render an empty Short" >&2
  exit 1
fi

# author_line.txt is written with printf and no trailing newline, so the author
# credit never hit the bug above and stays a single drawtext.
TEXT="${QUOTE_LAYERS},drawtext=fontfile=${FONT_REG}:textfile=author_line.txt:fontcolor=0xffd166:fontsize=${AUTHOR_SIZE}:borderw=2:bordercolor=black@0.6:x=(w-text_w)/2:y=(h-text_h)/2+160"
COVER="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"

shopt -s nullglob
bgs=(assets/backgrounds/*.mp4)
tracks=(assets/music/*.mp3)
shopt -u nullglob

# --- video source ---
if [ ${#bgs[@]} -gt 0 ]; then
  bg="${bgs[RANDOM % ${#bgs[@]}]}"
  echo "Background: $bg"
  video_in=(-stream_loop -1 -i "$bg")

  # Probe the clip's real dimensions so horizontal footage gets a native 9:16
  # treatment instead of losing ~2/3 of its width to a blind center-crop.
  dims=$(ffprobe -v error -select_streams v:0 \
           -show_entries stream=width,height -of csv=s=x:p=0 "$bg" 2>/dev/null \
           | head -n1) || dims=""
  w="${dims%%x*}"; h="${dims##*x}"
  case "${w}${h}" in ''|*[!0-9]*) w=0; h=0 ;; esac  # unparsable probe -> legacy path

  if [ "$h" -gt 0 ] && [ "$w" -gt "$h" ]; then
    echo "Horizontal clip (${w}x${h}) — fit mode: $BG_FIT"
    case "$BG_FIT" in
      blur)
        # Whole clip stays visible, centered over a blurred zoomed copy of itself.
        fit="split=2[fg][bgc];[bgc]${COVER},gblur=sigma=30[blurred];[fg]scale=1080:-2[scaled];[blurred][scaled]overlay=(W-w)/2:(H-h)/2"
        ;;
      pan)
        # Fill the height, then pan the 9:16 crop window across the width.
        fit="scale=-2:1920,crop=1080:1920:x='(iw-1080)*t/${DUR}':y=0"
        ;;
      crop)
        fit="$COVER"
        ;;
    esac
  else
    fit="$COVER"
  fi
  # Light darken (25%) keeps the scenery visible — the halo carries legibility.
  vf="${fit},drawbox=x=0:y=0:w=iw:h=ih:color=black@0.25:t=fill,${TEXT}"
else
  echo "No background clips — using solid color."
  video_in=(-f lavfi -i "color=c=0x0d1b2a:s=1080x1920:d=${DUR}")
  vf="${TEXT}"
fi

# --- audio source ---
if [ ${#tracks[@]} -gt 0 ]; then
  track="${tracks[RANDOM % ${#tracks[@]}]}"
  echo "Music: $track"
  # Record which track was used so upload_youtube.py can credit it (assets/music.json).
  basename "$track" > track.txt
  # Optional per-track start offset in seconds (music.json "start_at"); 0/absent = from the top.
  start=$(jq -r --arg t "$(basename "$track")" '.tracks[$t].start_at // 0' assets/music.json 2>/dev/null) || start=0
  case "$start" in ''|*[!0-9]*) start=0 ;; esac  # digits only — anything odd falls back to 0
  if [ "$start" -gt 0 ]; then
    echo "Music starts at ${start}s"
    audio_in=(-ss "$start" -i "$track")
  else
    audio_in=(-i "$track")
  fi
  af=(-af "afade=t=out:st=$((DUR-2)):d=2")
  acodec=(-c:a aac -b:a 192k)
else
  echo "No music — silent audio."
  : > track.txt
  audio_in=(-f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=44100")
  af=()
  acodec=(-c:a aac)
fi

ffmpeg -y "${video_in[@]}" "${audio_in[@]}" \
  -map 0:v -map 1:a \
  -vf "$vf" "${af[@]}" \
  -t ${DUR} -r 30 -c:v libx264 -pix_fmt yuv420p "${acodec[@]}" "$OUT_FILE"

echo "Rendered $OUT_FILE"
