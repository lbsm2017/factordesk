# Release checklist

Written 2026-11-18. The owner runs this list; nothing here is automated, and nothing in it has
been run for a real release. The packaging steps (3 to 5) were rehearsed locally on 2026-11-18
with version 0.1.0 and the result is recorded in `wiki/decision-python-and-uv-for-every-platform.md`.

Replace `X.Y.Z` with the version. Run commands from the repository root of a clean checkout of
the commit you are releasing. Never put a PyPI token in a file in this repository.

## 1. Prepare

- [ ] All work is merged through pull requests (see `wiki/decision-branches-and-pull-requests.md`)
      and the commit to release is on `prod`.
- [ ] `git status` is clean.
- [ ] Bump `version` in `pyproject.toml` to `X.Y.Z` (the `/api/health` version comes
      from the installed metadata, so there is no second place to edit).
- [ ] If uv's installer version should change, edit `UV_VERSION` in `scripts/install.sh` and
      `scripts/install.ps1` (both files, same value) and confirm that
      `https://astral.sh/uv/<UV_VERSION>/install.sh` exists.
- [ ] Commit the bump through a pull request, merge, and update your checkout.

## 2. Run the gates

```text
uv sync --locked
uv run pytest -q
uv run ruff check backend
uv run pyright
npm --prefix frontend ci
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run test
npm --prefix frontend run build
npm --prefix frontend run size
npm --prefix frontend run e2e
```

Every command must pass. CI runs the same gates on pull requests.

## 3. Build the page into the package

```text
npm --prefix frontend run build:package
```

This builds `frontend/dist` and copies it to `backend/factordesk/web/` (gitignored). The wheel
build stops with an error if that folder has no `index.html`, so a wheel without a dashboard
cannot be made by accident.

## 4. Build the wheel and the source archive

```text
rm -rf dist          # PowerShell: Remove-Item -Recurse -Force dist
uv build
```

- [ ] `dist/` holds `factordesk-X.Y.Z-py3-none-any.whl` and `factordesk-X.Y.Z.tar.gz`.
- [ ] The wheel lists the page, the fonts and the report stylesheet, and has no tests:

```text
python -m zipfile -l dist/factordesk-X.Y.Z-py3-none-any.whl
```

  Expect `factordesk/web/index.html`, `factordesk/web/assets/*.js`, `*.css`, four `*.woff2`,
  `factordesk/report/report.css` and `factordesk/report/fonts/*.woff2`. As of 2026-11-18 the
  wheel was about 0.5 MB with 53 files.

## 5. Test the wheel in a clean environment

Use a folder outside the repository, so nothing from the checkout can be found by accident:

```text
uv venv <temp>/wheel-test/venv --python 3.12
uv pip install --python <temp>/wheel-test/venv/bin/python dist/factordesk-X.Y.Z-py3-none-any.whl
cd <temp>/wheel-test
<temp>/wheel-test/venv/bin/factordesk --help
<temp>/wheel-test/venv/bin/factordesk serve --port 8123
```

(On Windows the interpreter and script are in `venv\Scripts\`.) In another terminal:

- [ ] `curl http://127.0.0.1:8123/api/health` answers `{"status":"ok","version":"X.Y.Z",...}`.
- [ ] `curl -i http://127.0.0.1:8123/` answers 200 with the page security headers.
- [ ] Every `/assets/...` address named in that page answers 200, including the four fonts.
- [ ] Open the page in a browser and look at it once. Stop the server with Ctrl+C.

## 6. Make the checksums

Put the two scripts next to the wheel, so one `SHA256SUMS` file covers everything you upload.

```text
cp scripts/install.sh scripts/install.ps1 dist/
cd dist
sha256sum factordesk-X.Y.Z-py3-none-any.whl factordesk-X.Y.Z.tar.gz install.sh install.ps1 > SHA256SUMS
cd ..
```

On Windows without `sha256sum`, use `Get-FileHash -Algorithm SHA256 <file>` for each file and
write the lines as `<lowercase hash>  <file name>` (two spaces).

- [ ] Run `sh dist/install.sh --version X.Y.Z --expect-sha256 <hash of install.sh> --dry-run` and
      `powershell -File dist\install.ps1 -Version X.Y.Z -ExpectSha256 <hash of install.ps1> -DryRun`.
      Both must print the plan and say nothing was installed.
- [ ] Paste the hashes of the two scripts into the release notes as well, so a reader can compare
      them against a second place.

## 7. Tag

```text
git tag -a vX.Y.Z -m "factordesk X.Y.Z"
git push origin vX.Y.Z
```

Tag the exact commit you built from. Do not move a tag afterwards; make a new version instead.

## 8. Publish

- [ ] Optional rehearsal: upload to TestPyPI (`uv publish --publish-url https://test.pypi.org/legacy/
      dist/factordesk-X.Y.Z*`) and install from it in a fresh environment.
- [ ] Upload to PyPI: `uv publish dist/factordesk-X.Y.Z-py3-none-any.whl dist/factordesk-X.Y.Z.tar.gz`.
      Use a project-scoped token or trusted publishing, passed through `UV_PUBLISH_TOKEN` in your
      shell, never in a file.
- [ ] Create the GitHub release for tag `vX.Y.Z`. Attach the wheel, the source archive,
      `install.sh`, `install.ps1` and `SHA256SUMS`.

## 9. Post-checks

On a machine or a fresh user account that has no checkout (and ideally no uv cache of this version):

- [ ] `uvx --from factordesk==X.Y.Z factordesk --help` works.
- [ ] `uvx --from factordesk==X.Y.Z factordesk serve --open` shows the dashboard.
- [ ] Follow "Install without cloning" in `docs/dashboard.md` on Windows, and on macOS or Linux, using
      the files downloaded from the release page. Confirm the checksum steps pass.
- [ ] Edit `docs/dashboard.md`: drop "(after the first release)" and the not-yet-working note.
- [ ] Mark the "One-shot install-and-run command" row in `docs/ROADMAP.md` as done, with the
      version and date.
- [ ] Add a dated line to `wiki/log.md`.
- [ ] If anything failed, yank the PyPI release (PyPI cannot replace files) and release `X.Y.Z+1`.
