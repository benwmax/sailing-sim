## Finishing the recorded clips on the Mac

Wikimedia rate-limited the cloud server after six downloads, so 24 of the 30 chosen Commons recordings are not in the
pack yet. A home connection is not throttled the same way. On the Mac (needs `python3` with `numpy`, and `ffmpeg`):

```sh
cd Inputs/audio/scripts
mkdir -p ../dl && cp commons_sources.json ../dl/meta.json
python3 slowfetch.py ../dl ../dl/meta.json      # downloads the 30 sources, waits politely on HTTP 429
python3 process.py ../dl ../Samples             # cuts loops and one-shots into Samples/
python3 make_docs.py ..                         # rebuilds README table, CREDITS.md and manifest.json
```

`process.py` holds the cut recipe for every source (target file, loop length, filter, use). Delete `../dl` afterwards;
the source recordings are not needed in the repo.
