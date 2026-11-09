"""Read aloud's Thai voices: the text front-end and the host-side steps of the Thai Kokoro model
(config/installer.yaml kokoro_th; tts.KokoroTh runs them).

  - g2p.py: Thai text (with English words in it) -> the model's phonemes, through pythainlp and tltk.
  - normalize.py: numbers, dates, abbreviations and symbols written out in Thai first (upstream's file, unchanged).
  - model.py: the three ONNX graphs and the harmonic source between them (numpy).

Adapted from kunato/wayu-kokoro-thai-v1 on Hugging Face (revision abf63dc118365bea784fa881bdd1dce4b2cc1fd4, the
serving bundle's kokoro_thai package), which its authors publish under the Apache License, Version 2.0
(http://www.apache.org/licenses/LICENSE-2.0). Each file says what was changed. Nothing here is imported until a Thai
voice reads: g2p and normalize need pythainlp and tltk, which only the Thai voices' Download installs.
"""
