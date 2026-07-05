#!/usr/bin/env bash
# Render a 1080x1920 vertical "Short" from the daily quote.
# Inputs (in the working directory): quote.txt, author.txt (raw text).
# Background: a random *.mp4 from assets/backgrounds/ (falls back to a solid color).
# Music:      a random *.mp3 from assets/music/       (falls back to silence).
# Output: out.mp4
set -euo pipefail

# ffmpeg is preinstalled on GitHub-hosted ubuntu runners; install if missing.
if ! command -v ffmpeg >/dev/null 2>&1; then
  sudo apt-get update -qq && sudo apt-get install -y -qq ffmpeg
fi

# drawtext does not auto-wrap, so wrap on spaces to fit the frame width.
fold -s -w 26 quote.txt > quote_wrapped.txt
printf '— %s' "$(cat author.txt)" > author_line.txt

FONT_BOLD="/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG="/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DUR=15

TEXT="drawtext=fontfile=${FONT_BOLD}:textfile=quote_wrapped.txt:fontcolor=white:fontsize=66:line_spacing=18:x=(w-text_w)/2:y=(h-text_h)/2-120,drawtext=fontfile=${FONT_REG}:textfile=author_line.txt:fontcolor=0xffd166:fontsize=46:x=(w-text_w)/2:y=(h-text_h)/2+280"

shopt -s nullglob
bgs=(assets/backgrounds/*.mp4)
tracks=(assets/music/*.mp3)
shopt -u nullglob

# --- video source ---
if [ ${#bgs[@]} -gt 0 ]; then
  bg="${bgs[RANDOM % ${#bgs[@]}]}"
  echo "Background: $bg"
  video_in=(-stream_loop -1 -i "$bg")
  # cover the frame (crop to 1080x1920), darken for legibility, then draw text.
  vf="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,drawbox=x=0:y=0:w=iw:h=ih:color=black@0.35:t=fill,${TEXT}"
else
  echo "No background clips — using solid color."
  video_in=(-f lavfi -i "color=c=0x0d1b2a:s=1080x1920:d=${DUR}")
  vf="${TEXT}"
fi

# --- audio source ---
if [ ${#tracks[@]} -gt 0 ]; then
  track="${tracks[RANDOM % ${#tracks[@]}]}"
  echo "Music: $track"
  audio_in=(-i "$track")
  af=(-af "afade=t=out:st=$((DUR-2)):d=2")
  acodec=(-c:a aac -b:a 192k)
else
  echo "No music — silent audio."
  audio_in=(-f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=44100")
  af=()
  acodec=(-c:a aac)
fi

ffmpeg -y "${video_in[@]}" "${audio_in[@]}" \
  -map 0:v -map 1:a \
  -vf "$vf" "${af[@]}" \
  -t ${DUR} -r 30 -c:v libx264 -pix_fmt yuv420p "${acodec[@]}" out.mp4

echo "Rendered out.mp4"
