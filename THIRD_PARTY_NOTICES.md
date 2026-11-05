# Third-Party Notices

`legends-ambient-intelligence` is released under the MIT License (`LICENSE`).

## Runtime Dependencies

The core package (`legends-ambient-intelligence`) uses only the Python 3.11+ standard library at runtime (`dependencies = []` in `pyproject.toml`).

## Optional Extras & External Tools (Not Bundled)

| Component | Upstream Project | License | Role |
| --- | --- | --- | --- |
| `faster-whisper` | [github.com/SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | Optional local Whisper ASR extra (`pip install ".[whisper]"`) |
| `FFmpeg` / `ffprobe` | [ffmpeg.org](https://ffmpeg.org) | LGPL-2.1+ / GPL-2.0+ (build-dependent) | Optional external audio binaries on `PATH` |
| `NVIDIA NeMo` / `Parakeet` | [github.com/NVIDIA/NeMo](https://github.com/NVIDIA/NeMo) | Apache-2.0 / CC-BY-4.0 | Optional external GPU ASR backend (`--backend parakeet`) |

See [NOTICE](NOTICE) for additional attribution details.
