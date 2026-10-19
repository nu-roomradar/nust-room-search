# AI 動画（Gemini／Veo など）のプロンプト

2026-10-17 に運営が Gemini で作った6本（`src/c0.mp4`〜`c5.mp4`）のもと。英語のままの方が意図どおりになりやすい。
動画の音は CM では使う部分だけ残すので、口の動きが英語の会話にならないよう「セリフなし」にしてある。

- Gemini（Veo）は1回で1本。下の【共通】のあとに【①】などの段落を付けて1本ずつ作る。
- 9:16 が選べなければ横で作ってよい（人物を中央に寄せる指示を入れてある）。
- 顔や手が崩れたもの、文字や看板が出たものは作り直す。

```
【共通】Characters (keep exactly the same look in every video):
- Character A: a Japanese female university student, about 20, shoulder-length dark brown hair, cream knit cardigan over a white T-shirt, light-blue wide jeans, canvas tote bag.
- Character B: a Japanese male university student, about 20, short black hair, round glasses, navy crewneck sweatshirt, beige chinos, black backpack.
- Character C: a Japanese female university student, about 20, high ponytail, light-blue striped shirt.
Style for every video: realistic, cinematic, natural daylight, warm and bright, shallow depth of field, gentle handheld movement, modern university building in Tokyo in autumn. Vertical 9:16 with the subjects centered. No text, no captions, no signs with readable text, no logos. No spoken dialogue: only ambient room sound and natural laughter. No music. Phone and laptop screens are never visible to the camera.

【①】End of class in a bright lecture room with long white desks and large windows. Students around them start packing up. Character A closes her notebook, stretches her arms with a relieved smile and stands up. Character B, next to her, stands up too; she turns to him and tilts her head with a playful "where should we go?" look, and they both laugh. Medium shot, camera slowly pushes in.

【②】In a bright hallway with large windows, Character B takes a smartphone out of his pocket and looks at it. After a second his face lights up with a satisfied grin, he gives a small nod, then turns to his side and gestures "follow me". Close-up to medium close-up.

【③】Character A slides open the door of a classroom and peeks inside; the room is completely empty and filled with soft sunlight. She turns back toward the camera with an excited, delighted expression and waves her friends in; Character B and Character C walk past the camera into the room. Camera follows from behind, slightly low angle.

【④】Character A sits at a desk by a large sunny window in an empty classroom, opens a laptop and starts typing with a relaxed, focused smile; a coffee cup and a notebook on the desk. Slow lateral camera move, close-medium shot, soft lens flare.

【⑤】Characters A, B and C sit together around desks in a bright, empty classroom doing group work with notebooks and a laptop; Character C does something funny and all three burst out laughing naturally. Medium shot, camera slowly circling.

【⑥】In a sunny classroom, Characters A, B and C stand up from their desks, high-five each other cheerfully and laugh, full of energy. Medium-wide shot, camera slightly low, bright backlight from the windows.
```

## 前回わかったこと

- 「warm and bright」だと金色の夕方っぽい光になり、AI らしさが出る。次は `natural overcast daylight, neutral colors` などにすると自然に寄る（v3 では切り出し時に色を直した）。
- ノートPCにリンゴのロゴが出た（④⑤）。`laptop without any logo` を足す。
- ⑥で緑の光の粒（レンズフレア）が出た。`no lens flare` を足す。
- 上下に黒い帯が入ることがある（④⑤⑥）。切り出しで落とせるが、解像度が下がる。
