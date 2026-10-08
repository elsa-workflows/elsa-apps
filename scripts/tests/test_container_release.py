import argparse
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import container_release as release


COMMIT = "1" * 40
ROOT_DIGEST = "sha256:" + "a" * 64
PLATFORMS = {
    "linux/amd64": "sha256:" + "b" * 64,
    "linux/arm64": "sha256:" + "c" * 64,
}


def args(**overrides):
    values = {
        "event": "workflow_dispatch",
        "version": "3.9.0",
        "publish": "true",
        "images": "server",
        "core_version": "3.9.0",
        "studio_version": "",
        "extensions_version": "3.9.0",
        "expected_commit": COMMIT,
        "release_tag": "",
        "ref": "refs/heads/main",
        "commit": COMMIT,
        "packages": "Directory.Packages.props",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class VersionAndSelectionTests(unittest.TestCase):
    def test_accepts_future_3x_semver_and_prereleases(self):
        for version in ("3.8.4", "3.9.0", "3.10.0", "3.9.1-rc.2", "3.10.0-preview.1"):
            with self.subTest(version=version):
                self.assertTrue(release.is_elsa_version(version))

    def test_rejects_non_3x_and_invalid_semver(self):
        for version in ("4.0.0", "3.9", "3.09.0", "3.9.0-01", "latest", "3.9.0+build.1"):
            with self.subTest(version=version):
                self.assertFalse(release.is_elsa_version(version))

    def test_selection_does_not_pull_in_unrelated_aliases(self):
        server = release.parse_image_selection("server")
        studio = release.parse_image_selection("studio-wasm")
        self.assertEqual([item["name"] for item in server], ["server"])
        self.assertEqual([item["name"] for item in studio], ["studio-wasm"])
        self.assertEqual(server[0]["aliases"][0]["name"], "server-alias")
        self.assertEqual(studio[0]["aliases"][0]["name"], "studio-wasm-alias")

    def test_wasm_profiles_use_dotnet_10_bootstrap_assets(self):
        for profile in ("studio-wasm", "studio-wasm-standalone", "server-studio-wasm"):
            with self.subTest(profile=profile):
                image = release.parse_image_selection(profile)[0]
                self.assertEqual(
                    image["smokeAssets"],
                    ["/_framework/dotnet.js", "/_framework/blazor.webassembly.js"],
                )

    def test_publication_source_and_expected_commit_are_pinned(self):
        run = release.resolve_run(args())
        self.assertEqual(run["sourceCommit"], COMMIT)
        self.assertEqual(run["requiredFamilies"], ["core", "extensions"])
        with self.assertRaisesRegex(release.ReleaseError, "main or the matching release tag"):
            release.resolve_run(args(ref="refs/heads/feature/release"))
        with self.assertRaisesRegex(release.ReleaseError, "expected_commit must equal"):
            release.resolve_run(args(expected_commit="2" * 40))
        with self.assertRaisesRegex(release.ReleaseError, "selected package families"):
            release.resolve_run(args(extensions_version=""))

    def test_build_only_subset_defaults_unused_family_from_repo_props(self):
        run = release.resolve_run(args(publish="false", core_version="", extensions_version=""))
        props = release.read_package_versions(Path("Directory.Packages.props"))
        self.assertEqual(run["packageVersions"]["studio"], props["ElsaStudioVersion"])

    def test_dispatch_does_not_allow_pr_publication(self):
        with self.assertRaisesRegex(release.ReleaseError, "Pull requests cannot publish"):
            release.validate_publication("pull_request", "3.9.0", True, "refs/pull/42/merge")


class ManifestPromotionTests(unittest.TestCase):
    def test_same_commit_published_from_main_is_reusable_from_matching_release_tag(self):
        package_versions = dict.fromkeys(("core", "studio", "extensions"), "3.9.0")
        original_labels = release.labels_for("3.9.0", COMMIT, "refs/heads/main", package_versions)
        manifest = {"digest": ROOT_DIGEST, "platforms": PLATFORMS}
        with (
            patch.object(release, "inspect_manifest", return_value=manifest),
            patch.object(release, "run_command", return_value=Mock(stdout=json.dumps(original_labels))),
        ):
            plan = release.get_image_plan_with_packages(
                "elsaworkflows/elsa-server-app", "3.9.0", COMMIT, "refs/tags/3.9.0", package_versions
            )
            self.assertTrue(plan["reuse"])
            self.assertEqual(plan["source_ref"], "elsaworkflows/elsa-server-app:3.9.0")
            original_labels["org.opencontainers.image.ref.name"] = "refs/heads/unreviewed"
            with patch.object(release, "run_command", return_value=Mock(stdout=json.dumps(original_labels))):
                with self.assertRaisesRegex(release.ReleaseError, "unapproved publication ref"):
                    release.get_image_plan_with_packages(
                        "elsaworkflows/elsa-server-app", "3.9.0", COMMIT, "refs/tags/3.9.0", package_versions
                    )

    def test_manifest_requires_exact_supported_platforms(self):
        with patch.object(release, "inspect_manifest", return_value={"digest": ROOT_DIGEST, "platforms": {**PLATFORMS, "linux/arm/v7": "sha256:" + "d" * 64}}):
            with self.assertRaisesRegex(release.ReleaseError, "unsupported platforms"):
                release.verify_manifest("elsaworkflows/test:3.9.0")

    def test_first_publish_promotes_source_before_alias_without_overwrite(self):
        image = release.parse_image_selection("server")[0]
        source_ref = f"{image['repository']}:3.9.0-sha-{COMMIT}"
        fragment = {
            "id": "server",
            "name": "server",
            "repository": image["repository"],
            "sourceRef": source_ref,
            "digest": ROOT_DIGEST,
            "platforms": [
                {"platform": platform, "digest": digest}
                for platform, digest in PLATFORMS.items()
            ],
            "smoke": {"success": True, "imageDigest": ROOT_DIGEST, "platforms": []},
            "resolvedPackages": {},
        }
        registry = {source_ref: {"digest": ROOT_DIGEST, "platforms": PLATFORMS}}
        created_tags = []

        def inspect(reference):
            return registry.get(reference)

        def verify(reference, expected_digest=None):
            result = registry.get(reference)
            if result is None:
                raise AssertionError(f"Tried to verify a destination before publishing it: {reference}")
            if expected_digest and result["digest"] != expected_digest:
                raise AssertionError("Unexpected digest mismatch")
            return result

        def command(command, **kwargs):
            if command[:5] == ["docker", "buildx", "imagetools", "create", "--tag"]:
                target = command[5]
                created_tags.append(target)
                registry[target] = {"digest": ROOT_DIGEST, "platforms": PLATFORMS}
            return None

        package_versions = {"core": "3.9.0", "studio": "3.9.0", "extensions": "3.9.0"}
        with (
            patch.object(release, "inspect_manifest", side_effect=inspect),
            patch.object(release, "verify_manifest", side_effect=verify),
            patch.object(release, "verify_labels"),
            patch.object(release, "run_command", side_effect=command),
        ):
            promoted = release.run_docker_promotion(
                [fragment], [image], "3.9.0", COMMIT, "refs/heads/main", package_versions
            )

        self.assertEqual(
            created_tags,
            [
                "elsaworkflows/elsa-server-app:3.9.0",
                "elsaworkflows/elsa-server:3.9.0",
            ],
        )
        self.assertEqual([item["name"] for item in promoted], ["server", "server-alias"])
        self.assertEqual(promoted[0]["digest"], ROOT_DIGEST)
        self.assertEqual(promoted[1]["alias_of"], "server")


class BrowserAssetSmokeTests(unittest.TestCase):
    class Response:
        status = 200

        def __init__(self, body, content_type):
            self.body = body
            self.headers = {"Content-Type": content_type}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return self.body

    def test_rejects_html_fallback_for_missing_javascript_asset(self):
        fallback = b"<!doctype html><html><body>Studio</body></html>" + b" " * 100
        with patch.object(
            release.urllib.request,
            "urlopen",
            return_value=self.Response(fallback, "application/javascript"),
        ):
            with self.assertRaisesRegex(release.ReleaseError, "HTML fallback page"):
                release.verify_smoke_assets("http://127.0.0.1:1234", ["/_framework/dotnet.js"])


class SmokeCredentialTests(unittest.TestCase):
    def test_ephemeral_credentials_are_shared_with_login_without_command_line_exposure(self):
        with (
            patch.object(release, "run_command", return_value=Mock(stdout="test-container")) as command,
            patch.object(release, "wait_for_http", return_value=("http://127.0.0.1:1234/", 200)),
            patch.object(release, "login_and_probe_api", return_value={}) as login,
        ):
            for _ in range(2):
                release.smoke_image("local-smoke", "linux/amd64", 8080, local=True, auth_enabled=True)
        starts = [call for call in command.call_args_list if call.args[0][:2] == ["docker", "run"]]
        passwords = []
        for start, probe in zip(starts, login.call_args_list):
            environment = start.kwargs["env"]
            password = environment["Identity__AdminUser__Password"]
            passwords.append(password)
            self.assertGreaterEqual(len(password), 32)
            self.assertNotIn(password, " ".join(start.args[0]))
            self.assertEqual(probe.args[1:], (environment["Identity__AdminUser__UserName"], password))
        self.assertEqual(len(passwords), 2)
        self.assertNotEqual(*passwords)


if __name__ == "__main__":
    unittest.main()
