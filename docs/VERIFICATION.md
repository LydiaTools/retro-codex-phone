# Verification for v0.1.0

Checked on 2026-09-29. This is an experimental source release, not a claim of universal handset support.

## Evidence from the development run

| Check | Result | What it establishes |
|---|---|---|
| 11 Python unit/integration tests | Pass on the development Mac | Button gestures, diagnostic mode, inactive-console guard, deliberate folder selection, agent argument construction, HTTP boundaries, error recovery |
| Real subprocess with a shell-looking prompt | Pass | The prompt reaches stdin unchanged; its shell syntax is not executed |
| Process timeout | Pass | The child is stopped and the runner can accept another task |
| Native macOS helper compilation | Pass with Swift 6.3.3 | The source builds; it does not establish physical media-key capture |
| JavaScript syntax | Pass with `node --check` | The console script parses |
| Desktop and 390 px mobile console | Inspected in Chrome | Fields and actions remain readable without horizontal overflow |
| Real WAV import through the console | Pass with faster-whisper 1.2.1, cached `small` model, CPU int8 | Audio reaches the local transcription pipeline and returns editable text |
| Transcript correction and Backspace | Pass in the browser | A recognition mistake can be corrected before a task is sent |

The imported sentence was "Don't laugh, this phone isn't a prop. It works." The recognizer produced "pop" instead of "prop". The text was corrected in the console. Speech recognition is fallible; review is part of the workflow. The default `base` model was not separately benchmarked in this run.

Codex was installed and its current `exec --help` was checked against the dispatch flags. Codex and Claude job construction was checked by tests; subprocess delivery was checked with a harmless stdin echo process. **No real model task was submitted to either provider in this acceptance run.** Claude Code was not installed on the development computer.

## Still needs physical or provider acceptance

- A handset microphone recording from the browser, including the adapter's input compatibility.
- Play/pause, plus and minus events from a physical handset; macOS permission behavior on the user's setup.
- A real Windows console/media-hook run. CI checks software behavior, not attached hardware.
- A signed-in Codex task and a signed-in Claude task, including their account-specific approval behavior.
- Browser/OS Read reply output through the handset.

Test media buttons with diagnostic mode enabled first. Use on-screen actions if an adapter exposes audio only. Unmodified RJ11 telephone-line phones are not supported.

## Reproduce the software checks

```sh
python -m unittest discover -s tests -v
node --check retro_phone/web/app.js
swiftc native/MediaButtons.swift -o /tmp/retro-phone-media-check  # macOS only
```

The GitHub workflow repeats the Python suite on Linux, macOS and Windows and compiles the Swift helper on macOS. Its status is visible under the repository's Actions tab.

No audio, account token, model, private prompt, or original studio video is included in the repository or starter ZIP. The console screenshot is from the actual running application.
