# Transcription Live Check

- date: 2026-05-31
- roadmap item: I-live transcription check
- result: blocked by missing downloaded native media candidate

## Checks

```powershell
python main.py transcribe backfill --limit 5 --dry-run
```

Result:

- attempted: 0
- transcribed/cached: 0
- failed: 0
- normalized files updated: 0

Additional scan:

- `media_cache/` contains downloaded image files, but no `*.mp4`, `*.mov`, `*.m4a`, `*.mp3`, `*.ogg`, `*.wav`, or
  `*.webm` files.
- `output/normalized/*.meta.json` has no current downloaded `video`, `audio`, or `voice` candidate for transcription
  backfill.

## Follow-up

To complete the live check, fetch or provide one short Telegram `voice`, `audio`, or native `video` item with
`download_status=downloaded`, configure a transcription-capable endpoint/model, then rerun:

```powershell
python main.py transcribe backfill --limit 1 --media-type voice
```

or the corresponding media type.
