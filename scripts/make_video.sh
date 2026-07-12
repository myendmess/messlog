#!/usr/bin/env bash
# Render a 1080x1920 vertical "Short" from the daily quote.
# Inputs (in the working directory): quote.txt, author.txt (raw text) — override
#   with QUOTE_FILE / AUTHOR_FILE for localized renders.
# Background: a random *.mp4 from assets/backgrounds/ (falls back to a solid color).
#   Vertical clips cover the frame (center-crop, unchanged legacy path).
#   Horizontal clips are fitted per BG_FIT: blur (default — full clip letterboxed
#   over a blurred copy of itself), pan (slow horizontal pan across the clip),
#   or crop (legacy hard center-crop).
# Music:      a random *.mp3 from assets/music/       (falls back to silence).
# Output: out.mp4 (override with OUT_FILE).
set -euo pipefail

# Overrides used by the localization pipeline and local testing.
QUOTE_FILE="${QUOTE_FILE:-quote.txt}"
AUTHOR_FILE="${AUTHOR_FILE:-author.txt}"
OUT_FILE="${OUT_FILE:-out.mp4}"
FONT_BOLD="${FONT_BOLD:-/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf}"
FONT_REG="${FONT_REG:-/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf}"
BG_FIT="${BG_FIT:-blur}"

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

TEXT="drawtext=fontfile=${FONT_BOLD}:textfile=quote_wrapped.txt:fontcolor=white:fontsize=66:line_spacing=18:x=(w-text_w)/2:y=(h-text_h)/2-120,drawtext=fontfile=${FONT_REG}:textfile=author_line.txt:fontcolor=0xffd166:fontsize=46:x=(w-text_w)/2:y=(h-text_h)/2+280"
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
  # Darken for legibility, then draw the text.
  vf="${fit},drawbox=x=0:y=0:w=iw:h=ih:color=black@0.35:t=fill,${TEXT}"
else
  echo "No background clips — using solid color."
  video_in=(-f lavfi -i "color=c=0x0d1b2a:s=1080x1920:d=${DUR}")
  vf="${TEXT}"
fi

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
  -map 0:v -map 1:a \
  -vf "$vf" "${af[@]}" \
  -t ${DUR} -r 30 -c:v libx264 -pix_fmt yuv420p "${acodec[@]}" "$OUT_FILE"

echo "Rendered $OUT_FILE"
