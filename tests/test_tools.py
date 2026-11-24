#!/usr/bin/env python3
# ps5-native-app-boilerplate - Host tooling regression tests.
# Copyright (C) 2026 BlackBearReloaded
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Exercises identity initialization and deployment resolution without a console.

from ftplib import error_perm
import hashlib
import json
import os
from pathlib import Path
from posixpath import dirname
import runpy
import shutil
import subprocess
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]


class ToolTests(unittest.TestCase):
    def run_init(self, param, **values):
        environment = os.environ.copy()
        environment.update(values)
        return subprocess.run(
            ["bash", str(ROOT / "tools/init-project.sh"), str(param)],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_init_coordinates_media_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            param = Path(directory) / "param.json"
            param.write_text(
                json.dumps(
                    {
                        "contentId": "UP9000-PPSA99999_00-HELLOWORLD000001",
                        "localizedParameters": {
                            "defaultLanguage": "en-US",
                            "en-US": {"titleName": "Old"},
                        },
                        "gameIntent": {"permittedIntents": [{"intentType": "launchActivity"}]},
                    }
                ),
                encoding="utf-8",
            )
            result = self.run_init(
                param,
                TITLE_ID="PPSA12345",
                APP_NAME="Moon Client",
                APP_CATEGORY="media",
                CONTENT_SUFFIX="MOONCLIENT000001",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            configured = json.loads(param.read_text(encoding="utf-8"))
            self.assertEqual(configured["titleId"], "PPSA12345")
            self.assertEqual(configured["conceptId"], "12345")
            self.assertEqual(configured["contentId"], "UP9000-PPSA12345_00-MOONCLIENT000001")
            self.assertEqual(configured["localizedParameters"]["en-US"]["titleName"], "Moon Client")
            self.assertEqual(configured["applicationCategoryType"], 65536)
            self.assertEqual(configured["contentBadgeType"], 2)
            self.assertNotIn("gameIntent", configured)

    def test_init_rejects_invalid_title_without_rewriting(self):
        with tempfile.TemporaryDirectory() as directory:
            param = Path(directory) / "param.json"
            original = '{"contentId":"UP9000-PPSA99999_00-HELLOWORLD000001"}\n'
            param.write_text(original, encoding="utf-8")
            result = self.run_init(param, TITLE_ID="PPSA12", APP_NAME="Broken")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(param.read_text(encoding="utf-8"), original)

    def test_init_derives_game_suffix_and_preserves_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            param = Path(directory) / "param.json"
            param.write_text(
                json.dumps(
                    {
                        "contentId": "UP9000-PPSA99999_00-HELLOWORLD000001",
                        "localizedParameters": {
                            "defaultLanguage": "en-US",
                            "en-US": {"titleName": "Old"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            param.chmod(0o640)
            result = self.run_init(
                param, TITLE_ID="PPSA54321", APP_NAME="Native Sample", CONTENT_SUFFIX=""
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            configured = json.loads(param.read_text(encoding="utf-8"))
            self.assertEqual(configured["contentId"], "UP9000-PPSA54321_00-NATIVESAMPLE0000")
            self.assertEqual(configured["applicationCategoryType"], 0)
            self.assertEqual(configured["contentBadgeType"], 1)
            self.assertEqual(
                configured["gameIntent"]["permittedIntents"],
                [{"intentType": "launchActivity"}],
            )
            self.assertEqual(param.stat().st_mode & 0o777, 0o640)

    def test_undeploy_dry_run_resolves_only_current_title(self):
        environment = os.environ.copy()
        environment.update(PS5_HOST="192.0.2.1", DEPLOY_DRY_RUN="1")
        result = subprocess.run(
            ["bash", str(ROOT / "tools/deploy.sh"), "undeploy"],
            cwd=ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("/data/homebrew/PPSA99999/", result.stdout)
        self.assertIn("PPSA99999.{ffpkg,ffpfsc}", result.stdout)
        self.assertIn("no network request was sent", result.stdout)

    def test_deploy_dry_run_uses_mocked_build_and_no_network(self):
        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)
            (sandbox / "tools").mkdir()
            (sandbox / "sce_sys").mkdir()
            shutil.copy2(ROOT / "tools/deploy.sh", sandbox / "tools/deploy.sh")
            (sandbox / "sce_sys/param.json").write_text(
                '{"titleId":"PPSA12345"}\n', encoding="utf-8"
            )

            mock_bin = sandbox / "mock-bin"
            mock_bin.mkdir()
            mock_make = mock_bin / "make"
            mock_make.write_text(
                "#!/usr/bin/env bash\n"
                "mkdir -p \"$MOCK_ROOT/dist\"\n"
                "printf '%s\\n' \"$*\" > \"$MOCK_ROOT/make-arguments\"\n"
                "mkdir -p \"$MOCK_ROOT/dist/PPSA12345/sce_sys\"\n"
                "printf app > \"$MOCK_ROOT/dist/PPSA12345/eboot.bin\"\n"
                "printf '{}' > \"$MOCK_ROOT/dist/PPSA12345/sce_sys/param.json\"\n",
                encoding="utf-8",
            )
            mock_make.chmod(0o755)

            environment = os.environ.copy()
            environment.update(
                PS5_HOST="192.0.2.1",
                DEPLOY_DRY_RUN="1",
                MOCK_ROOT=str(sandbox),
                PATH=f"{mock_bin}{os.pathsep}{environment['PATH']}",
            )
            result = subprocess.run(
                ["bash", str(sandbox / "tools/deploy.sh")],
                cwd=sandbox,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("/data/homebrew/PPSA12345/\n", result.stdout)
            self.assertIn("Would publish 2 files", result.stdout)
            self.assertIn("no network request was sent", result.stdout)
            # The build asked for is the app folder, never an image.
            arguments = sandbox / "make-arguments"
            self.assertEqual(arguments.read_text(encoding="utf-8").split()[-1], "app")

            # An image format is refused before anything is built.
            arguments.unlink()
            environment["DEPLOY_FORMAT"] = "ffpkg"
            refused = subprocess.run(
                ["bash", str(sandbox / "tools/deploy.sh")],
                cwd=sandbox,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(refused.returncode, 2, refused.stdout)
            self.assertIn("DEPLOY_FORMAT is no longer used", refused.stderr)
            self.assertFalse(arguments.exists())

    def test_ftp_replacement_survives_disconnect(self):
        publish = runpy.run_path(str(ROOT / "tools/deploy-folder.py"))["publish"]

        class MockFtp:
            def __init__(self):
                self.directories = {"/"}
                self.files = {}
                self.promoted = []
                self.current = "/"
                self.disconnect = None

            def pwd(self):
                return self.current

            def cwd(self, path):
                self.current = path

            def mlsd(self):
                return [
                    (path.rsplit("/", 1)[-1], {})
                    for path in self.files
                    if dirname(path) == self.current
                ]

            def mkd(self, path):
                if path in self.directories:
                    raise error_perm("550 Already exists")
                self.directories.add(path)

            def sendcmd(self, command):
                path = command.removeprefix("DELE ")
                if path not in self.files:
                    raise error_perm("550 No such file")
                if not path.endswith(".upload"):
                    raise AssertionError("deployment deleted a live file")
                del self.files[path]

            def storbinary(self, command, source, blocksize):
                self.files[command.removeprefix("STOR ")] = source.read()

            def rename(self, source, target):
                disconnect = self.disconnect if target.endswith("/eboot.bin") else None
                if disconnect == "before":
                    raise EOFError("connection dropped before rename")
                self.files[target] = self.files.pop(source)
                self.promoted.append(target)
                if disconnect == "after":
                    raise EOFError("rename reply was lost")

        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory)
            (artifact / "sce_sys").mkdir()
            (artifact / "banner.txt").write_bytes(b"asset")
            executable = artifact / "eboot.bin"
            metadata = artifact / "sce_sys/param.json"
            executable.write_bytes(b"initial binary")
            metadata.write_bytes(b"initial JSON")
            ftp = MockFtp()
            title = "PPSA12345"
            root = publish(ftp, title, artifact)
            live = root + "/eboot.bin"
            param = root + "/sce_sys/param.json"
            self.assertEqual(ftp.promoted, [root + "/banner.txt", live, param])
            self.assertEqual((ftp.files[live], ftp.files[param]), (b"initial binary", b"initial JSON"))

            for fault, expected in [("before", b"initial binary"), ("after", b"after")]:
                with self.subTest(fault=fault):
                    executable.write_bytes(fault.encode())
                    metadata.write_bytes(fault.encode() + b" JSON")
                    ftp.disconnect = fault
                    with self.assertRaises(EOFError):
                        publish(ftp, title, artifact)
                    self.assertEqual(ftp.files[live], expected)
                    previous = b"initial JSON" if fault == "before" else b"before JSON"
                    self.assertEqual(ftp.files[param], previous)
                    ftp.disconnect = None
                    publish(ftp, title, artifact)
                    self.assertEqual(ftp.files[live], executable.read_bytes())
                    self.assertEqual(ftp.files[param], metadata.read_bytes())
                    self.assertFalse(any(path.endswith(".upload") for path in ftp.files))

    def test_deploy_uses_selected_app_param_title(self):
        with tempfile.TemporaryDirectory() as directory:
            sandbox = Path(directory)
            (sandbox / "tools").mkdir()
            (sandbox / "sce_sys").mkdir()
            (sandbox / "examples/demo/sce_sys").mkdir(parents=True)
            shutil.copy2(ROOT / "tools/deploy.sh", sandbox / "tools/deploy.sh")
            (sandbox / "sce_sys/param.json").write_text(
                '{"titleId":"PPSA12345"}\n', encoding="utf-8"
            )
            selected_param = sandbox / "examples/demo/sce_sys/param.json"
            selected_param.write_text(
                '{"titleId":"PPSA54321"}\n', encoding="utf-8"
            )

            environment = os.environ.copy()
            environment.update(
                PS5_HOST="192.0.2.1",
                DEPLOY_DRY_RUN="1",
                APP_PARAM="examples/demo/sce_sys/param.json",
            )
            result = subprocess.run(
                ["bash", str(sandbox / "tools/deploy.sh"), "undeploy"],
                cwd=sandbox,
                env=environment,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("/data/homebrew/PPSA54321/", result.stdout)
            self.assertNotIn("/data/homebrew/PPSA12345/", result.stdout)

    @unittest.skipUnless(shutil.which("flock") and shutil.which("unzip"), "Linux SDK tools required")
    def test_sdk_recovery_and_concurrent_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "tools"
            tools.mkdir()
            script = tools / "setup-native-dependencies.sh"
            cache = root / ".deps/native"
            zlib = cache / "zlib/root"
            (zlib / "usr/include").mkdir(parents=True)
            (zlib / "usr/include/zlib.h").touch()
            (zlib / "libz.a").touch()
            script_text = (ROOT / "tools/setup-native-dependencies.sh").read_text()
            version = script_text.split('zlib_version="', 1)[1].split('"', 1)[0]
            (zlib / ".source-version").write_text(version + "\n")
            archive = cache / "ps5-payload-sdk.zip"
            with zipfile.ZipFile(archive, "w") as package:
                linker = zipfile.ZipInfo("ps5-payload-sdk/bin/prospero-lld")
                linker.create_system = 3
                linker.external_attr = 0o100755 << 16
                package.writestr(linker, "#!/bin/sh\n")
                package.writestr("ps5-payload-sdk/target/include/sample.h", "/* header */")
            digest = hashlib.sha256(archive.read_bytes()).hexdigest()
            pinned = script_text.split('sdk_hash="', 1)[1].split('"', 1)[0]
            script.write_text(script_text.replace(pinned, digest))
            mock_bin = root / "bin"
            mock_bin.mkdir()

            def mock(name, body):
                path = mock_bin / name
                path.write_text("#!/usr/bin/env bash\n" + body)
                path.chmod(0o755)

            mock("wget", "exit 99\n")
            mock("unzip", """
printf 'extract\\n' >> "$SDK_EXTRACT_LOG"
"$REAL_UNZIP" "$@" || exit
if [[ -f $SDK_FAIL_ONCE ]]; then
    rm -- "$SDK_FAIL_ONCE"
    exit 42
fi
""")
            trace = root / "extract.log"
            fail_once = root / "fail-once"
            fail_once.touch()
            env = dict(
                os.environ,
                PATH=f"{mock_bin}{os.pathsep}{os.environ['PATH']}",
                REAL_UNZIP=shutil.which("unzip"),
                SDK_EXTRACT_LOG=str(trace),
                SDK_FAIL_ONCE=str(fail_once),
            )
            command = ["bash", str(script)]
            first = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(first.returncode, 42, first.stderr)
            sdk = cache / "ps5-payload-sdk"
            self.assertFalse(sdk.exists())
            self.assertEqual(list(cache.glob(".sdk-stage.*")), [])

            with subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as one:
                with subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as two:
                    for process in (one, two):
                        _, error = process.communicate(timeout=20)
                        self.assertEqual(process.returncode, 0, error)
            self.assertEqual(trace.read_text().splitlines(), ["extract"] * 2)

            header = sdk / "target/include/sample.h"
            header.unlink()
            incomplete = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(incomplete.returncode, 0, incomplete.stderr)
            self.assertEqual(header.read_text(), "/* header */")
            warm = subprocess.run(command, env=env, capture_output=True, text=True)
            self.assertEqual(warm.returncode, 0, warm.stderr)
            self.assertEqual(trace.read_text().splitlines(), ["extract"] * 3)

    def test_pull_request_builds_are_named_and_labelled(self):
        workflow = (ROOT / ".github/workflows/tooling.yml").read_text(encoding="utf-8")
        self.assertIn(
            'echo "artifact=${GITHUB_REPOSITORY##*/}-PR$PR_NUMBER-$short" >> "$GITHUB_OUTPUT"',
            workflow,
        )
        self.assertIn('echo "BUILD_LABEL=PR $PR_NUMBER, $short" >> "$GITHUB_ENV"', workflow)
        self.assertIn("name: ${{ steps.label.outputs.artifact }}", workflow)
        # The release job still finds a tag's build under its commit.
        self.assertIn('--name "ps5-native-app-boilerplate-$GITHUB_SHA"', workflow)
        self.assertIn(
            'echo "artifact=ps5-native-app-boilerplate-$GITHUB_SHA" >> "$GITHUB_OUTPUT"', workflow
        )
        # A contributor's code is never built with write access or secrets.
        self.assertNotIn("pull_request_target:", workflow)
        build = (ROOT / "tools/build.sh").read_text(encoding="utf-8")
        self.assertIn('> "$app/build-label.txt"', build)
        self.assertIn("{1,40}$", build)
        self.assertLess(build.index("BUILD_LABEL must be"), build.index("ninja_run\n\napp="))
        self.assertIn('"/app0/build-label.txt"', (ROOT / "src/main.cpp").read_text())

    def test_automation_builds_the_zip_only(self):
        workflow = (ROOT / ".github/workflows/tooling.yml").read_text(encoding="utf-8")
        # The image formats are gone: nothing that builds may name them or their tools again.
        build_files = (
            ".github/workflows/tooling.yml",
            "Makefile",
            "build.ps1",
            "tools/build.sh",
        )
        for name in build_files:
            text = (ROOT / name).read_text(encoding="utf-8").lower()
            for gone in ("ffpfsc", "mkpfs", "ffpkg", "ufs2"):
                self.assertNotIn(gone, text, name)
        for name in (
            "setup-mkpfs-tooling.ps1",
            "setup-ffpkg-tooling.ps1",
            "setup-packaging-dependencies.sh",
        ):
            self.assertFalse((ROOT / "tools" / name).exists(), name)
        self.assertIn("run: make app", workflow)
        self.assertIn('sha256sum "$TITLE_ID.zip" > SHA256SUMS', workflow)
        self.assertIn('assets=("release/$FOLDER_ZIP" "release/$CHECKSUM")', workflow)
        # The release job creates a release, or fills one that has no ZIP; it never replaces,
        # deletes or rewrites anything on a release that exists.
        for forbidden in ("--clobber", "delete-asset", "gh release edit"):
            self.assertNotIn(forbidden, workflow)
        publish = workflow[workflow.index("- name: Publish GitHub release") :]
        self.assertIn('gh release create "$TAG" ', publish)
        self.assertIn('gh release upload "$TAG" ', publish)
        self.assertIn("--json assets --jq '.assets[].name'", publish)
        self.assertIn("if [[ $name == *.zip ]]; then", publish)
        self.assertIn("::warning title=Release files not from this run::", publish)
        self.assertLess(publish.index("gh release create"), publish.index("::warning"))
        self.assertLess(publish.index("::warning"), publish.index("gh release upload"))
        # The finished ZIP, and only the ZIP, is attested before it is uploaded: pinned action,
        # never for a pull request or in a private repository.
        attest = workflow.index("- name: Attest the release ZIP")
        upload = workflow.index("- name: Upload build")
        self.assertLess(workflow.index("- name: Write release checksums"), attest)
        self.assertLess(attest, upload)
        step = workflow[attest:upload]
        self.assertIn(
            "uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6 # v4.2.2", step
        )
        self.assertIn(
            "if: github.event_name != 'pull_request' && !github.event.repository.private", step
        )
        self.assertIn("subject-path: dist/${{ env.TITLE_ID }}.zip\n", step)
        self.assertNotIn("SHA256SUMS", step)
        build_job = workflow[workflow.index("\n  build:") : workflow.index("\n  release:")]
        for permission in ("contents: read", "id-token: write", "attestations: write"):
            self.assertIn(f"      {permission}\n", build_job)
        self.assertNotIn("id-token", workflow.replace(build_job, ""))
        # Asked for by name, the removed formats are refused before anything is built.
        for removed in ("Ffpkg", "Ffpfsc", "All"):
            result = subprocess.run(
                ["bash", str(ROOT / "tools/build.sh"), removed],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 2, removed)
            self.assertIn("usage: tools/build.sh [Folder]", result.stderr)

    def test_package_preserves_entry_contents_and_previous_archive_on_failure(self):
        package_app = runpy.run_path(str(ROOT / "tools/package-app.py"))["package_app"]
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            app = parent / "PPSA12345"
            (app / "empty").mkdir(parents=True)
            (app / "assets").mkdir()
            asset = app / "assets/large.bin"
            with asset.open("wb") as stream:
                for block in range(32):
                    stream.write(bytes([block]) * (256 * 1024))
            (app / "eboot.bin").write_bytes(b"example executable")
            old = parent / "old.zip"
            subprocess.run(
                ["python3", "-m", "zipfile", "-c", str(old), app.name], cwd=parent, check=True
            )

            current = parent / (app.name + ".zip")
            self.assertEqual(package_app(app, current), 5)
            with zipfile.ZipFile(old) as reference, zipfile.ZipFile(current) as archive:
                self.assertEqual(reference.namelist(), archive.namelist())
                self.assertIsNone(archive.testzip())
                for info in archive.infolist():
                    self.assertEqual(info.create_system, 3)
                    self.assertEqual((info.external_attr >> 16) & 0o777, 0o777)
                    with reference.open(info.filename) as before, archive.open(info) as after:
                        self.assertEqual(
                            hashlib.sha256(before.read()).digest(),
                            hashlib.sha256(after.read()).digest(),
                        )

            valid = current.read_bytes()
            (app / "missing-link").symlink_to(app / "absent")
            with self.assertRaises(FileNotFoundError):
                package_app(app, current)
            self.assertEqual(current.read_bytes(), valid)
            self.assertEqual(list(parent.glob(f".{current.name}.*")), [])


if __name__ == "__main__":
    unittest.main()
