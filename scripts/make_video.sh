#!/usr/bin/env bash
# Render a 1080x1920 vertical "Short" from the daily quote.
# Inputs (in the working directory): quote.txt, author.txt (raw text) — override
#   with QUOTE_FILE / AUTHOR_FILE for localized renders.
# Background: a random *.mp4 from assets/backgrounds/ (falls back to a solid color).
#   Vertical clips cover the frame (center-crop, unchanged legacy path).
#   Horizontal clips are fitted per BG_FIT: blur (default — full clip letterboxed
#   over a blurred copy of itself), pan (slow horizontal pan across the clip),
#   or crop (legacy hard center-crop).
# Text: quote in Aspire Demibold filled with a cyan->violet gradient (via a
#   maskedmerge of a gradients source through the glyphs) over a dark halo so it
#   stays readable at the light 20% darken; author in gold below. The quote
#   block sits in the upper half so the scenery stays visible.
# Music:      a random *.mp3 from assets/music/       (falls back to silence).
# Output: out.mp4 (override with OUT_FILE).
set -euo pipefail

# Overrides used by the localization pipeline and local testing.
QUOTE_FILE="${QUOTE_FILE:-quote.txt}"
AUTHOR_FILE="${AUTHOR_FILE:-author.txt}"
OUT_FILE="${OUT_FILE:-out.mp4}"
BG_FIT="${BG_FIT:-blur}"
# Quote font: Aspire Demibold (public domain, assets/font/info.txt) with a
# DejaVu fallback so a missing font can never kill the daily render.
ASPIRE="assets/font/AspireDemibold-YaaO.ttf"
DEJAVU_BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
DEJAVU_REG="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
if [ -z "${FONT_BOLD:-}" ]; then
  if [ -f "$ASPIRE" ]; then FONT_BOLD="$ASPIRE"; else FONT_BOLD="$DEJAVU_BOLD"; fi
fi
FONT_REG="${FONT_REG:-$DEJAVU_REG}"
# Gradient endpoints (quote fill), overridable per-run for A/B tests.
GRAD_FROM="${GRAD_FROM:-0x38bdf8}"   # sky blue
GRAD_TO="${GRAD_TO:-0xa855f7}"       # violet

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

# drawtext does not auto-wrap, so wrap on spaces to fit the frame width.
fold -s -w 26 "$QUOTE_FILE" > quote_wrapped.txt
printf '— %s' "$(cat "$AUTHOR_FILE")" > author_line.txt

DUR=15
echo "Quote font: $FONT_BOLD"

# Shared quote geometry — the halo pass and the gradient mask MUST match
# glyph-for-glyph, so both are built from this one string. The block is
# lifted well above center to leave the lower half for the scenery.
QUOTE_GEOM="fontfile=${FONT_BOLD}:textfile=quote_wrapped.txt:fontsize=60:line_spacing=16:x=(w-text_w)/2:y=(h-text_h)/2-320"
QUOTE_HALO="drawtext=${QUOTE_GEOM}:fontcolor=black:borderw=6:bordercolor=black@0.85"
QUOTE_MASK="drawtext=${QUOTE_GEOM}:fontcolor=white"
AUTHOR_DRAW="drawtext=fontfile=${FONT_REG}:textfile=author_line.txt:fontcolor=0xffd166:fontsize=44:borderw=2:bordercolor=black@0.6:x=(w-text_w)/2:y=(h-text_h)/2+160"
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
  # Light darken (20%) keeps the scenery visible — the text halo carries legibility.
  base_chain="${fit},drawbox=x=0:y=0:w=iw:h=ih:color=black@0.20:t=fill"
else
  echo "No background clips — using solid color."
  video_in=(-f lavfi -i "color=c=0x0d1b2a:s=1080x1920:d=${DUR}")
  base_chain="null"
fi

# Gradient-filled quote: [base + halo] -> maskedmerge pulls the gradient
# through the white-on-black glyph mask, leaving the dark halo as an outline.
# rgb24 keeps the merge clean (no half-strength chroma blending in yuv).
filter="
[0:v]${base_chain},${AUTHOR_DRAW},${QUOTE_HALO},format=rgb24[base];
gradients=s=1080x1920:c0=${GRAD_FROM}:c1=${GRAD_TO}:x0=0:y0=400:x1=1080:y1=1300:d=$((DUR+1)),format=rgb24[grad];
color=c=black:s=1080x1920:d=$((DUR+1)),${QUOTE_MASK},format=rgb24[mask];
[base][grad][mask]maskedmerge,format=yuv420p[vout]
"

# --- audio source ---
if [ ${#tracks[@]} -gt 0 ]; then
  track="${tracks[RANDOM % ${#tracks[@]}]}"
  echo "Music: $track"
  # Record which track was used so upload_youtube.py can credit it (music.json).
  basename "$track" > track.txt
  # Optional per-track start offset in seconds (music.json "start_at"); 0/absent = from the top.
  start=$(jq -r --arg t "$(basename "$track")" '.tracks[$t].start_at // 0' music.json 2>/dev/null) || start=0
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
  -filter_complex "$filter" \
  -map "[vout]" -map 1:a \
  "${af[@]}" \
  -t ${DUR} -r 30 -c:v libx264 -pix_fmt yuv420p "${acodec[@]}" "$OUT_FILE"

echo "Rendered $OUT_FILE"
