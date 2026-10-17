# docs

Each phase or fix round has its own folder of notes, benches and screenshots. The summaries are
`graphics-summary.md` and `visual-summary.md`.

## Screenshots

From Oct 17 2026, new screenshots under `docs/` are committed to plain git. Save them as JPEGs of about 300 KB or less;
`magick in.png -resize 1920x -quality 85 out.jpg` usually gets there. `docs/.gitattributes` turns LFS off for `.jpg`,
`.jpeg` and `.png` files under `docs/`. It lists the images committed through LFS before that date by name, so they
stay in LFS, and their history is not rewritten. Every other binary file, including everything under `Content/`, still
goes through LFS (the root `.gitattributes`).

Check where a new file will go with `git check-attr filter -- docs/<folder>/<file>.jpg`: `unset` means plain git.
