#!/usr/bin/env bash
# Render a 1080x1920 vertical "Short" from the daily quote.
# Inputs (in the working directory): quote.txt, author.txt (raw text).
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

ffmpeg -y \
  -f lavfi -i "color=c=0x0d1b2a:s=1080x1920:d=8" \
  -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=44100" \
  -vf "drawtext=fontfile=${FONT_BOLD}:textfile=quote_wrapped.txt:fontcolor=white:fontsize=66:line_spacing=18:x=(w-text_w)/2:y=(h-text_h)/2-120,drawtext=fontfile=${FONT_REG}:textfile=author_line.txt:fontcolor=0xffd166:fontsize=46:x=(w-text_w)/2:y=(h-text_h)/2+280" \
  -t 8 -r 30 -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest out.mp4

echo "Rendered out.mp4"
