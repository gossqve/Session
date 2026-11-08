"""Check reviewed file lists; optionally build a local, source-only ZIP.

No Git index, network or simulator operations are performed.
"""

import argparse
from datetime import datetime
from pathlib import Path, PurePosixPath
import zipfile


ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {".gitignore", "README.md", "AGENTS.md", "pyproject.toml"}
DOC_FILES = {"docs/ARCHITECTURE.md", "docs/REPOSITORY_FILES.md",
             "docs/s1d_verification.json"}
LIST_FILES = {"release/server_files.txt", "release/github_files.txt"}
FORBIDDEN = {".git", "__pycache__", ".venv", ".env", "runs", "outputs",
             "results", "artifacts", "tmp", "temp", ".pytest_cache"}


def read_files(target):
    """Return only existing, contained, approved input files, never directories."""
    names = (ROOT / "release" / f"{target}_files.txt").read_text(
        encoding="utf-8").splitlines()
    if not names or len(names) != len(set(names)):
        raise ValueError("Empty list or duplicate paths")
    for name in names:
        path = PurePosixPath(name)
        if (not name or "\\" in name or ":" in name or path.is_absolute()
                or any(p in {"", ".", ".."} for p in name.split("/"))
                or any(p in FORBIDDEN for p in path.parts)):
            raise ValueError(f"Unsafe path: {name}")
        allowed = (name in ROOT_FILES | DOC_FILES | LIST_FILES
                   or (path.parts[0] in {"src", "tests", "scripts"}
                       and path.suffix == ".py")
                   or (path.parts[0] == "configs" and path.suffix == ".json")
                   or (name.startswith("tests/fixtures/")
                       and path.suffix in {".json", ".csv", ".txt"})
                   or (name.startswith("docs/model_spec/")
                       and path.suffix == ".md"))
        if not allowed:
            raise ValueError(f"Unapproved input type: {name}")
        file = ROOT / name
        if not file.is_file() or file.is_symlink():
            raise ValueError(f"Missing file or symlink: {name}")
        if not file.resolve().is_relative_to(ROOT):
            raise ValueError(f"Path escapes repository: {name}")
    return names


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("server", "github"), required=True)
    parser.add_argument("--package", action="store_true",
                        help="Create a new ZIP under ignored runs/release_packages")
    args = parser.parse_args()
    names = read_files(args.target)
    print(f"Checked {len(names)} explicit {args.target} files")
    if args.package:
        directory = ROOT / "runs" / "release_packages"
        directory.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output = directory / f"session_{args.target}_{stamp}.zip"
        with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
            for name in names:
                archive.write(ROOT / name, arcname=name)
        with zipfile.ZipFile(output) as archive:
            if archive.namelist() != names or archive.testzip() is not None:
                raise RuntimeError("Archive verification failed")
        print(output.relative_to(ROOT).as_posix())


if __name__ == "__main__":
    main()
