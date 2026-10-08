import argparse
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
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


def correction_fixture():
    version = "3.9.0"
    prior_commit = "2" * 40
    run_id = "424242"
    attempt = 2
    package_versions = {family: version for family in ("core", "studio", "extensions")}
    platforms = {
        "linux/amd64": "sha256:" + "a" * 64,
        "linux/arm64": "sha256:" + "b" * 64,
    }
    receipt_images = []
    for index, image in enumerate(release.IMAGES):
        digest = "sha256:" + format(index + 4, "x") * 64
        entry = {
            "name": image["name"],
            "repository": image["repository"],
            "tag": version,
            "sourceRef": f"{image['repository']}:{version}-sha-{prior_commit}",
            "digest": digest,
            "platforms": [
                {"platform": platform, "digest": platform_digest}
                for platform, platform_digest in platforms.items()
            ],
            "registryVerified": True,
            "smoke": {"success": True},
            "packages": image["packages"],
            "packageVersions": {family: version for family in image["packages"]},
            "resolvedPackages": {},
        }
        receipt_images.append(entry)
    for image in release.IMAGES:
        canonical = next(entry for entry in receipt_images if entry["name"] == image["name"])
        for alias in image.get("aliases", []):
            receipt_images.append({
                **canonical,
                "name": alias["name"],
                "repository": alias["repository"],
                "alias_of": image["name"],
            })

    receipt = {
        "schemaVersion": 1,
        "releaseVersion": version,
        "appsRepository": release.APPS_REPOSITORY,
        "appsSource": {"ref": "refs/heads/main", "commit": prior_commit},
        "appsSourceCommit": prior_commit,
        "workflowRun": {
            "repository": release.APPS_REPOSITORY,
            "id": run_id,
            "runAttempt": attempt,
            "workflow": ".github/workflows/container-images.yml",
            "url": f"https://github.com/{release.APPS_REPOSITORY}/actions/runs/{run_id}",
            "event": "workflow_dispatch",
            "ref": "refs/heads/main",
            "headSha": prior_commit,
            "conclusion": "success",
        },
        "packageVersions": package_versions,
        "workflowInputs": {
            "version": version,
            "publish": True,
            "images": "all",
            "core_version": version,
            "studio_version": version,
            "extensions_version": version,
            "expected_commit": prior_commit,
        },
        "publication": "published",
        "images": receipt_images,
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zipped:
        zipped.writestr("container-release-receipt.json", json.dumps(receipt))
    archive = buffer.getvalue()
    run = {
        "id": int(run_id),
        "status": "completed",
        "conclusion": "success",
        "event": "workflow_dispatch",
        "path": ".github/workflows/container-images.yml@refs/heads/main",
        "html_url": f"https://github.com/{release.APPS_REPOSITORY}/actions/runs/{run_id}",
        "head_branch": "main",
        "head_repository": {"full_name": release.APPS_REPOSITORY},
        "repository": {"full_name": release.APPS_REPOSITORY},
        "head_sha": prior_commit,
        "run_attempt": attempt,
    }
    artifact = {
        "id": 812345,
        "name": f"container-release-receipt-{version}-{run_id}-{attempt}",
        "expired": False,
        "size_in_bytes": len(archive),
        "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
        "workflow_run": {"id": int(run_id), "head_sha": prior_commit, "head_branch": "main"},
    }
    return receipt, run, artifact, archive, package_versions


def correction_fragments():
    version = "3.9.0"
    commit = "3" * 40
    platforms = {
        "linux/amd64": "sha256:" + "c" * 64,
        "linux/arm64": "sha256:" + "d" * 64,
    }
    fragments = []
    for index, image in enumerate(release.IMAGES):
        fragments.append({
            "id": image["id"],
            "name": image["name"],
            "repository": image["repository"],
            "sourceRef": f"{image['repository']}:{version}-sha-{commit}",
            "digest": "sha256:" + format(index + 10, "x") * 64,
            "platforms": [
                {"platform": platform, "digest": digest}
                for platform, digest in platforms.items()
            ],
            "smoke": {"success": True},
            "resolvedPackages": {},
        })
    return fragments


def correction_registry(prior_by_reference, fragments, already_corrected=()):
    version = "3.9.0"
    registry = {}
    new_refs = {}
    for image, fragment in zip(release.IMAGES, fragments):
        manifest = {
            "digest": fragment["digest"],
            "platforms": {item["platform"]: item["digest"] for item in fragment["platforms"]},
        }
        registry[f"{image['repository']}@{fragment['digest']}"] = manifest
        new_refs[f"{image['repository']}:{version}"] = manifest
        for alias in image.get("aliases", []):
            new_refs[f"{alias['repository']}:{version}"] = manifest
    for reference, prior in prior_by_reference.items():
        registry[reference] = {"digest": prior["digest"], "platforms": prior["platforms"]}
    for reference in already_corrected:
        registry[reference] = new_refs[reference]
    return registry


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

    def test_supersede_is_full_version_published_main_dispatch_only(self):
        packages = {family: "3.9.0" for family in ("core", "studio", "extensions")}
        release.validate_supersede_request(
            "424242", "workflow_dispatch", "3.9.0", True, "refs/heads/main", list(release.IMAGES), packages
        )
        cases = (
            ("pull_request", True, "refs/heads/main", list(release.IMAGES), packages),
            ("workflow_dispatch", False, "refs/heads/main", list(release.IMAGES), packages),
            ("workflow_dispatch", True, "refs/heads/release", list(release.IMAGES), packages),
            ("workflow_dispatch", True, "refs/heads/main", list(release.IMAGES[:1]), packages),
            ("workflow_dispatch", True, "refs/heads/main", list(release.IMAGES), {**packages, "studio": "3.8.4"}),
        )
        for event, publish, ref, images, package_versions in cases:
            with self.subTest(event=event, publish=publish, ref=ref):
                with self.assertRaises(release.ReleaseError):
                    release.validate_supersede_request(
                        "424242", event, "3.9.0", publish, ref, images, package_versions
                    )


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
        digest_ref = f"{image['repository']}@{ROOT_DIGEST}"
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
        registry = {digest_ref: {"digest": ROOT_DIGEST, "platforms": PLATFORMS}}
        created_tags = []
        copied_sources = []

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
                copied_sources.append(command[6])
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
        self.assertEqual(copied_sources[0], digest_ref)
        self.assertEqual(copied_sources[1], f"{image['repository']}@{ROOT_DIGEST}")

    def test_conflicting_version_or_alias_tag_is_rejected_before_any_tag_creation(self):
        image = release.parse_image_selection("server")[0]
        fragment = server_fragment()
        digest_ref = f"{image['repository']}@{ROOT_DIGEST}"
        conflicts = (
            f"{image['repository']}:3.9.0",
            f"{image['aliases'][0]['repository']}:3.9.0",
        )
        package_versions = {"core": "3.9.0", "studio": "3.9.0", "extensions": "3.9.0"}
        expected_labels = release.labels_for("3.9.0", COMMIT, "refs/heads/main", package_versions)

        for conflict_ref in conflicts:
            with self.subTest(conflict_ref=conflict_ref):
                registry = {
                    digest_ref: {"digest": ROOT_DIGEST, "platforms": PLATFORMS},
                    conflict_ref: {"digest": "sha256:" + "e" * 64, "platforms": PLATFORMS},
                }
                commands = []

                def docker_command(command, **kwargs):
                    commands.append(command)
                    return Mock(stdout=json.dumps(expected_labels))

                with (
                    patch.object(release, "inspect_manifest", side_effect=registry.get),
                    patch.object(release, "run_command", side_effect=docker_command),
                ):
                    with self.assertRaisesRegex(release.ReleaseError, "conflicting|overwrite"):
                        release.run_docker_promotion(
                            [fragment], [image], "3.9.0", COMMIT, "refs/heads/main", package_versions
                        )
                self.assertFalse(
                    any(command[:4] == ["docker", "buildx", "imagetools", "create"] for command in commands)
                )

    def test_correction_plan_ignores_the_existing_version_tag(self):
        image = release.parse_image_selection("server")[0]
        candidate_ref = f"{image['repository']}:3.9.0-sha-{COMMIT}"
        manifest = {"digest": ROOT_DIGEST, "platforms": PLATFORMS}
        with (
            patch.object(release, "inspect_manifest", return_value=manifest) as inspect,
            patch.object(release, "verify_labels"),
        ):
            plan = release.get_image_plan_with_packages(
                image["repository"],
                "3.9.0",
                COMMIT,
                "refs/heads/main",
                {family: "3.9.0" for family in ("core", "studio", "extensions")},
                skip_version_tag=True,
            )
        self.assertEqual(plan["source_ref"], candidate_ref)
        self.assertTrue(plan["reuse"])
        self.assertEqual([call.args[0] for call in inspect.call_args_list], [candidate_ref, candidate_ref])


class SupersededPublicationTests(unittest.TestCase):
    def promote(self, registry, prior, receipt, packages, fragments, run_command):
        with (
            patch.object(release, "inspect_manifest", side_effect=registry.get),
            patch.object(release, "verify_labels"),
            patch.object(release, "run_command", side_effect=run_command),
        ):
            return release.run_docker_promotion(
                fragments,
                list(release.IMAGES),
                "3.9.0",
                "3" * 40,
                "refs/heads/main",
                packages,
                prior_by_reference=prior,
                prior_commit=receipt["appsSourceCommit"],
                prior_source_ref=receipt["appsSource"]["ref"],
                prior_package_versions=receipt["packageVersions"],
            )

    def prior_publication(self):
        receipt, run, artifact, archive, package_versions = correction_fixture()
        _receipt, references, supersedes = release.validate_superseded_archive(
            archive,
            artifact,
            expected_name=artifact["name"],
            run=run,
            version="3.9.0",
            package_versions=package_versions,
            repository=release.APPS_REPOSITORY,
        )
        return receipt, run, artifact, archive, package_versions, references, supersedes

    def test_verified_artifact_has_exact_receipt_member_and_all_eight_refs(self):
        _receipt, _run, artifact, _archive, _packages, references, supersedes = self.prior_publication()
        self.assertEqual(len(references), 8)
        self.assertEqual(len(supersedes["references"]), 8)
        self.assertEqual(supersedes["receiptArtifact"]["id"], artifact["id"])
        self.assertEqual(supersedes["receiptArtifact"]["archiveDigest"], artifact["digest"])

    def test_rejects_tampered_digest_and_extra_archive_members(self):
        _receipt, run, artifact, archive, packages = correction_fixture()
        with self.assertRaisesRegex(release.ReleaseError, "does not match GitHub artifact metadata"):
            release.validate_superseded_archive(
                archive + b"tampered",
                artifact,
                expected_name=artifact["name"],
                run=run,
                version="3.9.0",
                package_versions=packages,
                repository=release.APPS_REPOSITORY,
            )

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as zipped:
            zipped.writestr("container-release-receipt.json", json.dumps(_receipt))
            zipped.writestr("unexpected.json", "{}")
        extra_archive = buffer.getvalue()
        artifact["digest"] = "sha256:" + hashlib.sha256(extra_archive).hexdigest()
        with self.assertRaisesRegex(release.ReleaseError, "only container-release-receipt.json"):
            release.validate_superseded_archive(
                extra_archive,
                artifact,
                expected_name=artifact["name"],
                run=run,
                version="3.9.0",
                package_versions=packages,
                repository=release.APPS_REPOSITORY,
            )

    def test_loader_checks_canonical_successful_run_and_downloads_exact_artifact(self):
        _receipt, run, artifact, archive, packages = correction_fixture()
        current_commit = "3" * 40
        with (
            patch.object(release, "github_api_json", side_effect=[run, {"total_count": 1, "artifacts": [artifact]}]) as api,
            patch.object(release, "github_api_artifact_zip", return_value=archive) as download,
            patch.object(release.subprocess, "run", return_value=Mock(returncode=0)),
        ):
            _loaded, references, supersedes = release.load_superseded_publication(
                "424242",
                version="3.9.0",
                package_versions=packages,
                repository=release.APPS_REPOSITORY,
                current_run_id="777777",
                current_commit=current_commit,
            )
        self.assertEqual(len(references), 8)
        self.assertEqual(supersedes["appsSourceCommit"], run["head_sha"])
        self.assertEqual(api.call_args_list[0].args[0], "repos/elsa-workflows/elsa-apps/actions/runs/424242")
        self.assertEqual(
            api.call_args_list[1].args[0],
            "repos/elsa-workflows/elsa-apps/actions/runs/424242/artifacts?per_page=100",
        )
        download.assert_called_once_with("repos/elsa-workflows/elsa-apps/actions/artifacts/812345/zip")

    def test_correction_retry_promotes_prior_refs_and_leaves_latest_tags_out(self):
        receipt, _run, _artifact, _archive, packages, prior, _supersedes = self.prior_publication()
        fragments = correction_fragments()
        corrected_ref = "elsaworkflows/elsa-server:3.9.0"
        registry = correction_registry(prior, fragments, already_corrected=(corrected_ref,))
        created = []
        copied_sources = []

        def create_tag(command, **_kwargs):
            if command[:4] == ["docker", "buildx", "imagetools", "create"]:
                target, source = command[5], command[6]
                created.append(target)
                copied_sources.append(source)
                registry[target] = registry[source]
            return None

        promoted = self.promote(registry, prior, receipt, packages, fragments, create_tag)

        self.assertEqual(len(promoted), 8)
        self.assertEqual(len(created), 7)
        self.assertNotIn(corrected_ref, created)
        self.assertEqual(set(created), set(prior) - {corrected_ref})
        self.assertTrue(all("@sha256:" in source for source in copied_sources))

        created.clear()
        retry = self.promote(registry, prior, receipt, packages, fragments, create_tag)
        self.assertEqual(len(retry), 8)
        self.assertEqual(created, [])

    def test_drift_or_missing_tag_blocks_all_version_writes(self):
        receipt, _run, _artifact, _archive, packages, prior, _supersedes = self.prior_publication()
        fragments = correction_fragments()
        affected_ref = "elsaworkflows/elsa-studio:3.9.0"

        for state in ("drift", "missing"):
            with self.subTest(state=state):
                registry = correction_registry(prior, fragments)
                if state == "drift":
                    registry[affected_ref] = {
                        "digest": "sha256:" + "f" * 64,
                        "platforms": {"linux/amd64": "sha256:" + "e" * 64, "linux/arm64": "sha256:" + "d" * 64},
                    }
                else:
                    del registry[affected_ref]
                create_tag = Mock()
                with self.assertRaises(release.ReleaseError):
                    self.promote(
                        registry,
                        prior,
                        receipt,
                        packages,
                        fragments,
                        create_tag,
                    )
                self.assertFalse(
                    any(call.args[0][:4] == ["docker", "buildx", "imagetools", "create"] for call in create_tag.call_args_list)
                )


def server_fragment():
    image = release.parse_image_selection("server")[0]
    platforms = [
        {"platform": platform, "digest": digest}
        for platform, digest in PLATFORMS.items()
    ]
    smoke_platforms = [
        {
            "platform": platform,
            "imageDigest": digest,
            "status": "success",
            "httpStatus": 200,
            "browserAssets": [],
            "identityLogin": {"status": 200, "endpoint": "/elsa/api/identity/login"},
            "bearerApi": {"status": 200, "endpoint": "/elsa/api/workflow-definitions?page=0&pageSize=1"},
        }
        for platform, digest in PLATFORMS.items()
    ]
    return {
        "id": image["id"],
        "name": image["name"],
        "repository": image["repository"],
        "sourceRef": f"{image['repository']}:3.9.0-sha-{COMMIT}",
        "digest": ROOT_DIGEST,
        "platforms": platforms,
        "smoke": {"success": True, "imageDigest": ROOT_DIGEST, "platforms": smoke_platforms},
        "resolvedPackages": {
            "core": [{"id": "Elsa", "version": "3.9.0"}],
            "extensions": [{"id": "Elsa.Logging", "version": "3.9.0"}],
        },
    }


class ImageArtifactSelectionTests(unittest.TestCase):
    def test_newest_attempt_wins_independent_of_download_order_and_retains_earlier_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = []
            for profile, attempt in (("server", 1), ("studio-wasm", 1), ("server", 2)):
                directory = root / f"container-image-{profile}-12345-{attempt}"
                directory.mkdir()
                artifact_file = directory / f"{profile}.json"
                artifact_file.write_text("{}", encoding="utf-8")
                paths.append(artifact_file)
            selected_images = release.parse_image_selection("server,studio-wasm")

            forward = release.select_latest_image_artifacts(paths, selected_images, "12345", 2)
            reverse = release.select_latest_image_artifacts(list(reversed(paths)), selected_images, "12345", 2)
            self.assertEqual([(item["id"], item["runAttempt"]) for item in forward], [
                ("server", 2), ("studio-wasm", 1)
            ])
            self.assertEqual(forward, reverse)

    def test_rejects_missing_wrong_run_future_duplicate_and_unknown_artifacts(self):
        selected_images = release.parse_image_selection("server")
        cases = (
            ([], "Missing"),
            ([Path("/tmp/container-image-server-99999-1/server.json")], "belongs to run"),
            ([Path("/tmp/container-image-server-12345-3/server.json")], "future attempt"),
            ([Path("/tmp/container-image-server-12345-0/server.json")], "invalid/future attempt"),
            ([Path("/tmp/container-image-unknown-12345-1/unknown.json")], "unknown profile"),
            ([
                Path("/tmp/container-image-server-12345-1/server.json"),
                Path("/tmp/container-image-server-12345-1/server.json"),
            ], "Duplicate"),
        )
        for paths, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(release.ReleaseError, message):
                    release.select_latest_image_artifacts(paths, selected_images, "12345", 2)

    def test_fragment_profile_must_match_artifact_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            artifact_dir = Path(temporary) / "container-image-server-12345-1"
            artifact_dir.mkdir()
            (artifact_dir / "server.json").write_text(json.dumps({"id": "studio-wasm"}), encoding="utf-8")
            selected = release.select_latest_image_artifacts(
                [artifact_dir / "server.json"], release.parse_image_selection("server"), "12345", 1
            )
            with self.assertRaisesRegex(release.ReleaseError, "contains profile"):
                release.read_fragments(selected, release.parse_image_selection("server"))


class FinalizeEvidenceRejectionTests(unittest.TestCase):
    def run_finalize_with_fragment(self, fragment):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        artifact_dir = root / f"container-image-server-12345-1"
        artifact_dir.mkdir()
        (artifact_dir / "server.json").write_text(json.dumps(fragment), encoding="utf-8")
        command = [
            "finalize", "--publication", "published", "--version", "3.9.0",
            "--commit", COMMIT, "--source-ref", "refs/heads/main", "--images", "server",
            "--core-version", "3.9.0", "--studio-version", "3.9.0", "--extensions-version", "3.9.0",
            "--event", "workflow_dispatch", "--repository", "elsa-workflows/elsa-apps",
            "--run-id", "12345", "--run-attempt", "2", "--expected-commit", COMMIT,
            "--artifact-dir", str(root), "--output-file", str(root / "receipt.json"),
        ]
        with (
            patch.object(release, "run_command") as create_tag,
            patch.object(release, "inspect_manifest") as inspect,
        ):
            result = release.main(command)
        self.assertEqual(result, 1)
        create_tag.assert_not_called()
        inspect.assert_not_called()

    def test_missing_platform_smoke_is_rejected_before_any_tag_creation(self):
        fragment = server_fragment()
        fragment["smoke"]["platforms"].pop()
        self.run_finalize_with_fragment(fragment)

    def test_mismatched_resolved_package_is_rejected_before_any_tag_creation(self):
        fragment = server_fragment()
        fragment["resolvedPackages"]["core"][0]["version"] = "3.8.4"
        self.run_finalize_with_fragment(fragment)

    def test_receipt_records_selected_earlier_evidence_attempt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact_dir = root / "container-image-server-12345-1"
            artifact_dir.mkdir()
            fragment = server_fragment()
            fragment["sourceRef"] = f"elsa-local-server:3.9.0-{COMMIT}"
            fragment["platforms"] = [{"platform": "linux/amd64", "digest": ROOT_DIGEST}]
            fragment["smoke"]["platforms"] = fragment["smoke"]["platforms"][:1]
            fragment["smoke"]["platforms"][0]["imageDigest"] = ROOT_DIGEST
            (artifact_dir / "server.json").write_text(json.dumps(fragment), encoding="utf-8")
            receipt_path = root / "receipt.json"
            command = [
                "finalize", "--publication", "build-only", "--version", "3.9.0",
                "--commit", COMMIT, "--source-ref", "refs/heads/main", "--images", "server",
                "--core-version", "3.9.0", "--studio-version", "3.9.0", "--extensions-version", "3.9.0",
                "--event", "workflow_dispatch", "--repository", "elsa-workflows/elsa-apps",
                "--run-id", "12345", "--run-attempt", "2", "--expected-commit", COMMIT,
                "--artifact-dir", str(root), "--output-file", str(receipt_path),
            ]
            self.assertEqual(release.main(command), 0)
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["workflowRun"]["runAttempt"], 2)
            self.assertEqual(
                receipt["imageEvidence"],
                [{
                    "profile": "server",
                    "artifactName": "container-image-server-12345-1",
                    "runId": "12345",
                    "runAttempt": 1,
                }],
            )


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


class AuthenticatedApiSmokeTests(unittest.TestCase):
    class Response:
        status = 200

        def __init__(self, body, content_type="application/json"):
            self.body = body
            self.headers = {"Content-Type": content_type}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return self.body

    def test_uses_bearer_protected_workflow_definitions_api_and_validates_paged_json(self):
        login = self.Response(b'{"accessToken":"synthetic-token"}')
        definitions = self.Response(b'{"items":[],"totalCount":0}')
        requests = []

        def open_url(request, timeout):
            requests.append(request)
            return (login, definitions)[len(requests) - 1]

        with patch.object(release.urllib.request, "urlopen", side_effect=open_url):
            result = release.login_and_probe_api("http://127.0.0.1:1234/", "smoke", "secret")

        self.assertEqual(requests[0].full_url, "http://127.0.0.1:1234/elsa/api/identity/login")
        self.assertEqual(requests[0].get_method(), "POST")
        self.assertEqual(
            requests[1].full_url,
            "http://127.0.0.1:1234/elsa/api/workflow-definitions?page=0&pageSize=1",
        )
        self.assertEqual(requests[1].get_method(), "GET")
        self.assertEqual(requests[1].get_header("Authorization"), "Bearer synthetic-token")
        self.assertEqual(result["bearerApi"]["status"], 200)

    def test_rejects_html_fallback_even_when_it_returns_http_200(self):
        login = self.Response(b'{"accessToken":"synthetic-token"}')
        fallback = self.Response(b'<!doctype html><html>Studio</html>', "text/html; charset=utf-8")
        with patch.object(release.urllib.request, "urlopen", side_effect=[login, fallback]):
            with self.assertRaisesRegex(release.ReleaseError, "invalid JSON"):
                release.login_and_probe_api("http://127.0.0.1:1234", "smoke", "secret")

    def test_rejects_non_paged_json_response(self):
        login = self.Response(b'{"accessToken":"synthetic-token"}')
        invalid = self.Response(b'{"message":"not the workflow list"}')
        with patch.object(release.urllib.request, "urlopen", side_effect=[login, invalid]):
            with self.assertRaisesRegex(release.ReleaseError, "paged JSON response"):
                release.login_and_probe_api("http://127.0.0.1:1234", "smoke", "secret")

    def test_login_and_api_timeouts_name_the_failed_endpoint(self):
        with patch.object(release.urllib.request, "urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaisesRegex(release.ReleaseError, "identity/login failed"):
                release.login_and_probe_api("http://127.0.0.1:1234", "smoke", "secret")

        login = self.Response(b'{"accessToken":"synthetic-token"}')
        with patch.object(release.urllib.request, "urlopen", side_effect=[login, TimeoutError("timed out")]):
            with self.assertRaisesRegex(release.ReleaseError, "workflow definitions API request.*failed"):
                release.login_and_probe_api("http://127.0.0.1:1234", "smoke", "secret")

    def test_asset_timeout_names_the_failed_asset(self):
        with patch.object(
            release.urllib.request,
            "urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            with self.assertRaisesRegex(release.ReleaseError, "asset request for /_framework/dotnet.js failed"):
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

    def test_smoke_errors_include_image_and_platform_without_credentials(self):
        with (
            patch.object(release.secrets, "token_urlsafe", return_value="known-smoke-password"),
            patch.object(release, "run_command", return_value=Mock(stdout="test-container")),
            patch.object(release, "wait_for_http", return_value=("http://127.0.0.1:1234/", 200)),
            patch.object(release, "login_and_probe_api", side_effect=release.ReleaseError("API request timed out")),
        ):
            with self.assertRaisesRegex(
                release.ReleaseError,
                r"registry/image:3\.8\.4 on linux/arm64: API request timed out",
            ) as error:
                release.smoke_image(
                    "registry/image:3.8.4",
                    "linux/arm64",
                    8080,
                    auth_enabled=True,
                )
        self.assertNotIn("known-smoke-password", str(error.exception))
        self.assertNotIn("container-smoke", str(error.exception))


if __name__ == "__main__":
    unittest.main()
