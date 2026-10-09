"""Tokenizer assets persist in /share across Needle Trainer container rebuilds."""

from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))

from tokenizer_assets import (  # noqa: E402
    download_assets,
    install_offline,
    verify_assets,
)


class TokenizerAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.work = self.root / "share"
        self.package = self.root / "installed-needle-model"
        self.assets = self.work / "tokenizer"

    def test_offline_training_rejects_missing_tokenizer_preemptively(self) -> None:
        with self.assertRaisesRegex(
            FileNotFoundError, "mode=download_tokenizer"
        ):
            install_offline(self.work, needle_model_dir=self.package)
        self.assertFalse(self.package.exists())

    def test_explicit_download_persists_both_assets(self) -> None:
        remote = self.root / "hub"
        remote.mkdir()
        for name in ("tokenizer.model", "tokenizer.vocab"):
            (remote / name).write_bytes(("needle3-" + name).encode())
        calls = []

        def fake_hf_hub_download(*, repo_id, filename, repo_type):
            calls.append((repo_id, filename, repo_type))
            return str(remote / Path(filename).name)

        fake_hub = types.SimpleNamespace(
            hf_hub_download=fake_hf_hub_download
        )
        with patch.dict(sys.modules, {"huggingface_hub": fake_hub}):
            paths = download_assets(self.work)
            self.assertEqual(len(paths), 2)
            self.assertEqual(len(calls), 2)
            self.assertEqual(
                calls[0],
                ("Cactus-Compute/needle3", "tokenizer/tokenizer.model", "model"),
            )
            self.assertEqual(
                paths[0].read_bytes(), b"needle3-tokenizer.model"
            )
            download_assets(self.work)
            self.assertEqual(len(calls), 2, "Cached assets must not refetch")

    def test_offline_install_uses_shared_files_without_network(self) -> None:
        self.assets.mkdir(parents=True)
        (self.assets / "tokenizer.model").write_bytes(b"tokenizer-needle3")
        (self.assets / "tokenizer.vocab").write_bytes(b"vocab-needle3")
        with patch.dict(sys.modules, {"huggingface_hub": None}):
            paths = install_offline(
                self.work, needle_model_dir=self.package
            )
        self.assertEqual([p.name for p in paths], [
            "tokenizer.model", "tokenizer.vocab"
        ])
        self.assertEqual(
            (self.package / "tokenizer.model").read_bytes(),
            b"tokenizer-needle3",
        )
        self.assertEqual(len(verify_assets(self.work)), 2)

    def test_reinstallation_replaces_equal_length_outdated_tokenizer(self) -> None:
        self.assets.mkdir(parents=True)
        self.package.mkdir(parents=True)
        (self.assets / "tokenizer.model").write_bytes(b"new-model")
        (self.assets / "tokenizer.vocab").write_bytes(b"new-vocab")
        (self.package / "tokenizer.model").write_bytes(b"old-model")
        (self.package / "tokenizer.vocab").write_bytes(b"old-vocab")
        install_offline(self.work, needle_model_dir=self.package)
        self.assertEqual(
            (self.package / "tokenizer.model").read_bytes(), b"new-model"
        )
        self.assertEqual(
            (self.package / "tokenizer.vocab").read_bytes(), b"new-vocab"
        )


if __name__ == "__main__":
    unittest.main()
