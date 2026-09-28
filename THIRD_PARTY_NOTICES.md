# Sources and licenses

Retro Codex Phone is an independent implementation. No AI-Commander or AIDeskPhone source is bundled or relabelled.

Related implementations researched before development:

- [YuJonny/AI-Commander](https://github.com/YuJonny/AI-Commander), MIT © 2026 Jonny Yu. It provides existing media-key/voice-input precedent and includes Codex/Claude shortcut presets. Our workflow comparison credits it openly.
- [Damue01/AIDeskPhone](https://github.com/Damue01/AIDeskPhone), a separate ESP32/desk-phone hardware project. Its firmware or assets are not included.
- [Handy](https://github.com/cjpais/Handy), a separate desktop transcription alternative. Its code or binaries are not included.

Runtime dependency:

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper), MIT. Installed through the normal Python package manager, not vendored here. Its dependencies retain their own licenses.
- Whisper model files are downloaded separately by the operator. See [OpenAI Whisper](https://github.com/openai/whisper) for the upstream model/code license. No model files, API tokens or credentials are included in this repository or release ZIP.

Native adapters and console code in this repository are written for this project under the root MIT LICENSE.
