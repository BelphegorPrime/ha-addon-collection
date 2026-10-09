"""Persistent Needle 3 tokenizer assets for fully offline HA-local training.

Explicit download mode fetches from the public Needle HF repository. Offline
mode copies assets from the shared workspace into the version-pinned Needle
package directory: upstream get_tokenizer() searches only that directory and
otherwise attempts to download, which fails with HF_HUB_OFFLINE=1.
"""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

HF_REPO = "Cactus-Compute/needle3"
ASSETS = ("tokenizer.model", "tokenizer.vocab")


def shared_dir(work: Path) -> Path:
    return work / "tokenizer"


def verify_assets(work: Path) -> tuple[Path, ...]:
    """Fail immediately before expensive JAX initialization."""
    files = tuple(shared_dir(work) / name for name in ASSETS)
    for path in files:
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(
                f"Missing {path}. Run mode=download_tokenizer (or mode=download) "
                "once while online; training and calibration stay offline."
            )
    return files


def _atomic_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.name + ".partial")
    try:
        with src.open("rb") as reader, tmp.open("wb") as writer:
            shutil.copyfileobj(reader, writer, length=1024 * 1024)
            writer.flush()
            os.fsync(writer.fileno())
        if tmp.stat().st_size == 0:
            raise ValueError(f"Empty tokenizer source: {src}")
        os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)


def download_assets(work: Path) -> tuple[Path, ...]:
    """Network use is restricted to an explicitly selected download mode."""
    from huggingface_hub import hf_hub_download

    output = shared_dir(work)
    output.mkdir(parents=True, exist_ok=True)
    for name in ASSETS:
        dest = output / name
        if dest.is_file() and dest.stat().st_size > 0:
            print(f"Tokenizer cached: {dest}", flush=True)
            continue
        cached = Path(
            hf_hub_download(
                repo_id=HF_REPO,
                filename=f"tokenizer/{name}",
                repo_type="model",
            )
        )
        _atomic_copy(cached, dest)
        print(f"Tokenizer downloaded: {dest}", flush=True)
    return verify_assets(work)


def install_offline(
    work: Path, *, needle_model_dir: Path | None = None
) -> tuple[Path, ...]:
    """Make the shared tokenizer visible to upstream get_tokenizer(), no HF."""
    sources = verify_assets(work)
    if needle_model_dir is None:
        from needle.model import tokenizer

        needle_model_dir = Path(tokenizer.TOKENIZER_DIR)
    outputs = []
    for src in sources:
        dest = needle_model_dir / src.name
        # Package site-packages are rebuilt on add-on upgrades, while the
        # original copy always survives in the Supervisor /share volume.
        # Always refresh on process start: same-length tokenizer revisions
        # must not leave stale package-local assets.
        _atomic_copy(src, dest)
        outputs.append(dest)
    print(
        f"Offline tokenizer ready: {needle_model_dir / 'tokenizer.model'}",
        flush=True,
    )
    return tuple(outputs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("download", "install"))
    parser.add_argument("work", type=Path)
    args = parser.parse_args(argv)
    if args.operation == "download":
        download_assets(args.work)
    else:
        install_offline(args.work)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
