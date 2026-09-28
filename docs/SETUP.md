# Connect your handset

## 1. Check the hardware first

A USB handset that exposes a microphone, or a TRRS headset-style handset with a compatible input adapter, can be used as an audio input. A headset output-only jack will not carry microphone audio. An unmodified telephone-line/RJ11 phone is not supported by this software.

In the system Sound settings, check whether the handset appears as an input device and whether the input meter moves when you speak. Then use **Find microphones** in the console and select that device. The browser permission is for the local console, not for a cloud transcription service.

Media buttons are a second test. Enable **Phone buttons**, leave **Test buttons without sending** on, and press play/pause, plus and minus. The console should list the detected events. A detected play/pause key alone does not prove that the adapter also exposes plus/minus.

If the device has no usable buttons, the on-screen Record/Send/Backspace controls provide the same software workflow. You can also use an external media-key remote that exposes standard media events.

## 2. Prepare an agent

- **Codex:** install/sign in using the [official Codex CLI guide](https://developers.openai.com/codex/cli). Check `codex --version` in the same terminal that launches the console.
- **Claude Code:** install/sign in using [Anthropic's setup guide](https://code.claude.com/docs/en/quickstart). Check `claude --version` in that terminal.

The console reports whether it can find each CLI on PATH. It does not import account tokens, scrape desktop sessions, or call undocumented endpoints.

Choose an existing folder for the coding project. Codex defaults to `--sandbox read-only`; Claude defaults to `--permission-mode plan`. To let the agent make normal project edits, turn on **Allow edits in this project** before sending. Approvals or blocked operations still belong to the agent; this tool never supplies bypass flags. Use the normal agent terminal for tasks requiring interactive approvals.

Each send starts a separate CLI job. This version does not resume previous jobs automatically. Include the context you want in the prompt.

## 3. Start voice

Click **Prepare local voice** once. On first use, this downloads the selected Whisper model; subsequent runs reuse the cache. Use `python -m retro_phone --model tiny` for a smaller model, or `--model /path/to/downloaded/model --offline` for an existing model. English and other Whisper-supported languages use the same pipeline; accuracy varies with model, accent, noise and microphone.

Click Record or double-tap play/pause with test mode off. Double-tap again to stop. Wait for the transcript, edit it if necessary, then press plus/Send. Minus is backspace in the staged prompt. Clear removes the entire prompt and reply. An active job will not be sent twice.

WAV import is available for testing your microphone recordings without keeping a live microphone open. Recordings must be below 12 MB. Browser recordings stop after 110 seconds.

For a slower double-tap gesture, launch with `--double-tap-ms 650`. The supported range is 100–1000 ms; the default is 420 ms.

## 4. Platform notes

### macOS

The on-screen console works without a native key listener. Phone buttons require the Swift helper. Install Apple's Xcode command-line tools if you want to build that helper from source. When macOS requests Input Monitoring/Accessibility for the terminal, Python launcher or `MediaButtons`, review and enable the appropriate item yourself in System Settings. Retry Enable after changing permissions. No security setting is changed by the launcher.

### Windows

Use Python 3.11 x64 and `start-windows.bat`. The user-enabled listener reads only play/pause and volume up/down media codes. The window must not be running at a privilege level different from the launcher. Windows hardware acceptance is still pending for this release.

### Audio output

For Read reply through the handset, select it as your system audio output device. The console does not change global microphone or speaker settings automatically.

## Troubleshooting

| Symptom | Check |
|---|---|
| No transcript | Correct browser microphone permission/input; speech in the selected device; prepared model; noise level |
| Audio works, buttons do not | Adapter exposes standard media events; macOS listener permissions; test mode status |
| CLI not found | Install the CLI, open a new terminal, verify `--version`, then launch here |
| CLI reports login/approval error | Use its normal sign-in or interactive terminal; no bypass is attempted |
| Slow first use | Model download is a one-time step; transcription runs on CPU with two threads |
| Plus did not send during recording | Stop the recording, wait for the transcript, then send the reviewed text |
| Console disconnected | The terminal must stay open; check that port 8768 is free or use `--port 8769` |
