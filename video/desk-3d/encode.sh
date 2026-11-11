#!/usr/bin/env bash
# コマ（renders/frames/）と音（music.py の renders/audio_raw.wav）をつないで、Instagram 向けの mp4 にする。
# 音量は -14 LUFS 前後（上げて、はみ出す山だけ抑える）。映像は 1080x1920・30fps・H.264（yuv420p）、音は AAC ステレオ 128kbps。
set -euo pipefail
cd "$(dirname "$0")"
OUT="${1:-renders/cm5-desk-3d-v1.mp4}"
ffmpeg -hide_banner -loglevel error -y -i renders/audio_raw.wav -af "volume=5.6dB,alimiter=limit=0.84:attack=3:release=120:level=false" -ar 48000 renders/audio.wav
ffmpeg -hide_banner -loglevel error -y -framerate 30 -i renders/frames/%05d.jpg -i renders/audio.wav \
  -c:v libx264 -preset slow -crf 15 -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709 -movflags +faststart \
  -c:a aac -b:a 128k -ar 48000 -ac 2 -shortest "$OUT"
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,pix_fmt,channels:format=duration,size -of default=nw=1 "$OUT"
ffmpeg -hide_banner -nostats -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -E "^ +I:|Peak:" | tail -2
