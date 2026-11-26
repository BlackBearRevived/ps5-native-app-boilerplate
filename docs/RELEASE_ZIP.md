# Build output and releases

Every application build creates and validates `dist/<TITLE_ID>/` and archives
it as `dist/<TITLE_ID>.zip`. On Windows, `./build.ps1` runs the same build
through WSL.

```bash
make app
```

The build uses Python's standard-library `zipfile` module to archive
`dist/<TITLE_ID>/` as `<TITLE_ID>.zip`. Extract the ZIP before directory
deployment. The catalog and in-app updater use this format.
The packaging tool (`tools/package-app.py`) streams files into the archive and sets
every entry to `0777` as it writes. The console requires accessible files and some
extractors preserve the archived mode. The tool checks permissions and CRCs before
replacing the previous ZIP.

CI also installs the published [ps5-pkgkit v0.1.0 wheel](https://github.com/BlackBearRevived/ps5-pkgkit/releases/tag/v0.1.0)
with pip and checks the wheel against a pinned SHA-256. It builds and verifies
`<TITLE_ID>.pkg` from the same staged folder for free Games-area apps.
Media-area apps and other metadata outside the wheel's supported scope receive
the ZIP. The PKG has its own checksum file so ZIP consumers can keep using
`SHA256SUMS` with just the ZIP.

## Publishing a release

Update `contentVersion` in `sce_sys/param.json` and push or merge the release
commit to `main`. For metadata version `01.000.000`, the workflow creates tag
`1.000.000` at the commit it built. It uploads the ZIP and `SHA256SUMS`, plus
the PKG and `<TITLE_ID>.pkg.sha256` for supported titles. A later push with the
same version retains the published release and tag. Bump `contentVersion` for
a new release.

For public builds outside pull requests, a dedicated job checks the downloaded
files and signs GitHub Actions build provenance for both formats when present.
A public release waits for that job to succeed. The publish job checks the
release files again and confirms that the tag points to the built commit.

## Verify a downloaded release

Use a recent GitHub CLI. For a ZIP, run the following from the directory with
both the ZIP and its checksum file.

```bash
sha256sum -c SHA256SUMS
repo=BlackBearRevived/ps5-native-app-boilerplate
tag=1.000.000
source_sha=$(gh api "repos/$repo/commits/$tag" --jq .sha)
gh attestation verify PPSA99999.zip --repo "$repo" \
  --signer-workflow "$repo/.github/workflows/tooling.yml" \
  --source-digest "$source_sha" --deny-self-hosted-runners
```

Use the desired release tag and the actual filename. To check a PKG, run
`sha256sum -c PPSA99999.pkg.sha256` and pass `PPSA99999.pkg` to the same
attestation command. The attestation verifies the file's bytes, the
GitHub-hosted signing workflow, and the source commit for the tag.
See [GitHub artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations).
