# Daily Quote

**A fresh motivational quote committed here every morning — and auto-published as a vertical YouTube Short set to a my&mess track.**

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/github/license/myendmess/daily-quote?color=blue"></a>
  <a href="https://github.com/myendmess/daily-quote/actions/workflows/blank.yml"><img alt="Daily Quote workflow" src="https://img.shields.io/github/actions/workflow/status/myendmess/daily-quote/blank.yml?label=daily%20quote&logo=githubactions&logoColor=white"></a>
</p>

<p align="center">
  <a href="https://myendmess.github.io/daily-quote/"><img alt="Landing page" src="https://img.shields.io/badge/GitHub%20Pages-live-fbbf24?logo=googlechrome&logoColor=black"></a>
  <a href="https://www.youtube.com/playlist?list=PLNiOPtRmph_w"><img alt="Motivational playlist" src="https://img.shields.io/badge/YouTube-motivational%20playlist-red?logo=youtube&logoColor=white"></a>
  <a href="https://open.spotify.com/track/3T4WZ84ukDuik3TAlz6HCX"><img alt="Vespero on Spotify" src="https://img.shields.io/badge/Spotify-Vespero-1DB954?logo=spotify&logoColor=white"></a>
</p>

<p align="center">
  <a href="https://myendmess.github.io/daily-quote/"><b>Landing page</b></a> ·
  <a href="https://www.youtube.com/playlist?list=PLNiOPtRmph_w"><b>Motivational Playlist</b></a> ·
  <a href="https://open.spotify.com/track/3T4WZ84ukDuik3TAlz6HCX"><b>Vespero on Spotify</b></a>
</p>

### Adding a new song

New music can go on the landing page (Spotify embed), into the daily-Short rotation, or both.

- **Website — song is on the album?** Nothing to do — the album embed in `index.html` shows it automatically.
- **Website — new single/EP?** In Spotify: Share → Embed, copy the `src` URL. Duplicate the `// the album` section in `index.html` and swap in the new URL (keep `?utm_source=generator`, drop any `&si=` token).
- **Website — changing the featured track** (top card): edit `featured` in `music.json`.
- **Shorts rotation:** drop the `.mp3` into `assets/music/` *only if* it should score Shorts — `make_video.sh` picks a random `.mp3` from that folder each day. Then add a `music.json` `tracks` entry keyed by the **exact filename** (`name`, `artist`, optional `spotify_track_id`/`youtube_id`) so the Short's description credits it.
- **Start mid-song:** optional `"start_at"` (seconds) in a track's entry makes the Short's audio begin there — e.g. Ash & Blade uses `159` (= 2:39).

### Adding a new Short background

- Drop a `.mp4` into `assets/backgrounds/` — one is picked at random per Short.
- Any length works (it loops); it's center-cropped to 1080×1920 and darkened 35% for text legibility, so calm, low-detail footage reads best.
- Have a **pic** instead of a clip? Convert it first:
  `ffmpeg -loop 1 -i pic.jpg -t 15 -r 30 -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920" -pix_fmt yuv420p assets/backgrounds/pic.mp4`
- Note for this section only: keep headings at `###` level — the daily workflow inserts each new quote above the first `## ` heading in this file.

---

## 2026-07-10

> A warrior does not give up what he loves, he finds the love in what he does.

— Dan Millman

## 2026-07-10

> Every time we liberate a woman, we liberate a man.

— Margaret Mead

## 2026-07-09

> Someone is sitting in the shade today because someone planted a tree a long time ago.

— Warren Buffett

## 2026-07-08

> Hardly anybody recognizes the most significant moments of their life at the time they happen.

— W.P. Kinsella

## 2026-07-07

> Cease striving. Then there will be transformation.

— Zhuangzi

## 2026-07-06

> A good system shortens the road to the goal.

— Orison Swett Marden

## 2026-07-05

> There is no value in anything until it is finished.

— Genghis Khan

## 2026-07-05

> Everything is created twice, first in the mind and then in reality.

— Robin Sharma

## 2026-07-05

> Conquer the devils with a little thing called love.

— Bob Marley

## 2026-07-05

> Bad things are not the worst things that an happen to us. NOTHING is the worst thing that can happen to us.

— Richard Bach

## 2026-07-05

> Others can stop you temporarily - you are the only one who can do it permanently.

— Zig Ziglar

## 2026-07-04

> Your vision will become clear only when you can look into your own heart.

— Lolly Daskal

## 2026-07-03

> Curiosity is the most powerful thing you own. Imagination is a force that can actually manifest a reality.

— James Cameron

## 2026-07-02

> Genius is the ability to act rightly without precedent - the power to do the right thing the first time.

— Elbert Hubbard

## 2026-07-01

> I never said it would be easy, I only said it would be worth it.

— Mae West

## 2026-06-30

> Why do you stay in prison when the door is so wide open?

— Rumi

## 2026-06-29

> The more you like yourself, the less you are like anyone else, which makes you unique.

— Walt Disney

## 2026-06-28

> You don't get in life what you want; you get in life what you are.

— Les Brown

## 2026-06-27

> By failing to prepare, you are preparing to fail.

— Benjamin Franklin

## 2026-06-26

> Everything is possible. The impossible just takes longer.

— Dan Brown

## 2026-06-25

> To share your weakness is to make yourself vulnerable; to make yourself vulnerable is to show your strength.

— Criss Jami

## 2026-06-24

> Go for it now. The future is promised to no one.

— Wayne Dyer

## 2026-06-23

> You must live in the present, launch yourself on every wave, find your eternity in each moment. Fools stand on their island of opportunities and look toward another land. There is no other land; there is no other life but this.

— Henry David Thoreau

## 2026-06-22

> You're braver than you believe, and stronger than you seem, and smarter than you think.

— A.A. Milne

## 2026-06-21

> The spirit is beyond destruction. No one can bring an end to spirit which is everlasting.

— Bhagavad Gita

## 2026-06-20

> You're always free to change your mind and choose a different future, or a different past.

— Richard Bach

## 2026-06-19

> We forge the chains we wear in life.

— Charles Dickens

## 2026-06-18

> Gratitude is the fairest blossom which springs from the soul.

— Henry Ward Beecher

## 2026-06-17

> If fear is too strong, the genius is suppressed.

— Robert Kiyosaki

## 2026-06-16

> What people say, what people do, and what they say they do are entirely different things.

— Margaret Mead

## 2026-06-15

> Unless someone truly has the power to say no, they never truly have the power to say yes.

— Dan Millman

## 2026-06-15

> The highest level of wisdom is when you not only accept but love adversity.

— Maxime Lagace

## 2026-06-14

> Do good by stealth, and blush to find it fame.

— Alexander Pope

## 2026-06-13

> Procrastination is attitude's natural assassin. There's nothing so fatiguing as an uncompleted task.

— William James

## 2026-06-12

> He who laughs at himself never runs out of things to laugh at.

— Epictetus
