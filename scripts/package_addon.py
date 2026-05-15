#!/usr/bin/env python3

import argparse
import json
import shutil
import zipfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
STAGE_ROOT = DIST_DIR / "_stage"
STAGE_DIR = STAGE_ROOT / "medical_card_generator"
ZIP_PATH = DIST_DIR / "medical_card_generator.zip"

INCLUDED_PATHS = [
    "__init__.py",
    "manifest.json",
    "config.json",
    "config.md",
    "README.md",
    "core",
    "ui",
    "docs",
    "scripts",
]


def build_package(include_local_api_key: bool) -> Path:
    if STAGE_ROOT.exists():
        shutil.rmtree(STAGE_ROOT)
    STAGE_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    for rel_path in INCLUDED_PATHS:
        src = REPO_ROOT / rel_path
        dst = STAGE_DIR / rel_path
        if src.is_dir():
            shutil.copytree(
                src,
                dst,
                ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc", "*.pyo"),
            )
        elif src.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    if include_local_api_key:
        meta_path = REPO_ROOT / "meta.json"
        if meta_path.exists():
            config_path = STAGE_DIR / "config.json"
            config = json.loads(config_path.read_text())
            meta = json.loads(meta_path.read_text())
            meta_conf = meta.get("config", {})

            anthropic_key = meta_conf.get("provider_api_keys", {}).get("anthropic")
            if anthropic_key:
                config.setdefault("provider_api_keys", {})["anthropic"] = anthropic_key
            if meta_conf.get("api_key"):
                config["api_key"] = meta_conf["api_key"]

            for key in [
                "provider",
                "model",
                "default_deck",
                "cards_per_topic",
                "temperature",
                "max_tokens",
                "auto_add_disclaimer_card",
                "domain_hints",
            ]:
                if key in meta_conf:
                    config[key] = meta_conf[key]

            config_path.write_text(json.dumps(config, indent=4) + "\n")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in STAGE_ROOT.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(STAGE_ROOT))

    shutil.rmtree(STAGE_ROOT)
    return ZIP_PATH


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a clean Anki add-on zip.")
    parser.add_argument(
        "--include-local-api-key",
        action="store_true",
        help="Read the current local API key from meta.json and embed it in the packaged config.json.",
    )
    args = parser.parse_args()

    zip_path = build_package(include_local_api_key=args.include_local_api_key)
    print(zip_path)


if __name__ == "__main__":
    main()
