#!/usr/bin/env bash
# コマと音をつないで、Instagram 向けの mp4 にする。
#   bash encode.sh                          … 机の上の版（renders/frames ＋ renders/audio_raw.wav → renders/cm5-desk-3d-v2.mp4）
#   bash encode.sh door                     … ポスターとドアの版（renders/frames_door ＋ renders/audio2_raw.wav → renders/cm6-poster-door-v1.mp4）
# 音量は -14 LUFS 前後（上げて、はみ出す山だけ抑える）。映像は 1080x1920・30fps・H.264（yuv420p）、音は AAC ステレオ 128kbps。
set -euo pipefail
cd "$(dirname "$0")"
if [ "${1:-}" = "door" ]; then FR=renders/frames_door; AU=renders/audio2_raw.wav; OUT=renders/cm6-poster-door-v4.mp4; GAIN=6.4
else FR=renders/frames; AU=renders/audio_raw.wav; OUT=renders/cm5-desk-3d-v2.mp4; GAIN=5.6; fi
ffmpeg -hide_banner -loglevel error -y -i "$AU" -af "volume=${GAIN}dB,alimiter=limit=0.84:attack=3:release=120:level=false" -ar 48000 "${AU%_raw.wav}.wav"
ffmpeg -hide_banner -loglevel error -y -framerate 30 -i "$FR/%05d.jpg" -i "${AU%_raw.wav}.wav" \
  -c:v libx264 -preset slow -crf 21 -pix_fmt yuv420p -colorspace bt709 -color_primaries bt709 -color_trc bt709 -movflags +faststart \
  -c:a aac -b:a 128k -ar 48000 -ac 2 -shortest "$OUT"
ffprobe -v error -show_entries stream=codec_name,width,height,r_frame_rate,pix_fmt,channels:format=duration,size -of default=nw=1 "$OUT"
ffmpeg -hide_banner -nostats -i "$OUT" -af ebur128=peak=true -f null - 2>&1 | grep -E "^ +I:|Peak:" | tail -2
