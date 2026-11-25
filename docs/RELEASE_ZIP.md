# Build output and release ZIP

Every application build creates and validates `dist/<TITLE_ID>/` and archives
it as `dist/<TITLE_ID>.zip`. The folder and its ZIP are the only outputs; on
Windows, `./build.ps1` runs the same build through WSL.

Tagged GitHub Releases and every CI build attach a ZIP of the validated
directory-style application and its `SHA256SUMS`, and nothing else.

```bash
make app
```

The release workflow uses Python's standard-library `zipfile` module to archive
`dist/<TITLE_ID>/` as `<TITLE_ID>.zip`. The ZIP is a distribution convenience,
not another console filesystem format; extract it before directory deployment.
The packaging tool (`tools/package-app.py`) streams files into the archive and sets
every entry to `0777` as it writes. The console requires accessible files and some
extractors preserve the archived mode. The tool checks permissions and CRCs before
replacing the previous ZIP.

## Publishing a release

Update `contentVersion` in `sce_sys/param.json` and push or merge the release
commit to `main`. For metadata version `01.000.000`, the workflow creates tag
`1.000.000` at the commit it built. It uploads the folder-format ZIP and its
`SHA256SUMS` as the release assets. A later push with the same version retains
the published ZIP and tag. Bump `contentVersion` for a new release.

For public builds outside pull requests, a dedicated job checks the downloaded
ZIP and signs GitHub Actions build provenance for it. A public release waits
for that job to succeed. The publish job checks the same build's ZIP again
and confirms that the tag points to the built commit. GitHub indexes the
attestation by the ZIP's hash.

## Verify a downloaded release

Use a recent GitHub CLI. From the directory with the ZIP and checksum file:

```bash
sha256sum -c SHA256SUMS
repo=BlackBearRedux/ps5-native-app-boilerplate
tag=1.000.000
source_sha=$(gh api "repos/$repo/commits/$tag" --jq .sha)
gh attestation verify PPSA99999.zip --repo "$repo" \
  --signer-workflow "$repo/.github/workflows/tooling.yml" \
  --source-digest "$source_sha" --deny-self-hosted-runners
```

Use the desired release tag and the actual ZIP filename. This verifies the
ZIP's bytes, the GitHub-hosted signing workflow, and the source commit for the
tag. See [GitHub artifact attestations](https://docs.github.com/en/actions/concepts/security/artifact-attestations).
