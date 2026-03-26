#!/usr/bin/env python3
"""
Bootstrap a local Cortex installation on macOS.

Checks dependencies, clones/updates the repo, runs migrations,
and writes the skill connection config.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

CORTEX_DIR = Path.home() / "Projects" / "cortex"
CORTEX_REPO = "https://github.com/MatteoCui001/cortex.git"
SKILL_CONFIG_PATH = Path.home() / ".cortex" / "skill_config.yaml"
DEFAULT_API_PORT = 8420
DEFAULT_RELAY_PORT = 8421


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    """Run a command, printing it first."""
    print(f"  $ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, **kwargs)


def _cmd_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _check_python() -> str:
    """Return python3 path; require 3.12+."""
    for py in ("python3.14", "python3.13", "python3.12", "python3"):
        path = shutil.which(py)
        if path:
            result = subprocess.run(
                [path, "-c", "import sys; print(sys.version_info[:2])"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                major, minor = eval(result.stdout.strip())
                if major >= 3 and minor >= 12:
                    return path
    return ""


def _check_postgres() -> str:
    """Find psql; support both PATH and Homebrew locations."""
    if _cmd_exists("psql"):
        return shutil.which("psql")
    # Homebrew PostgreSQL 16/17
    for ver in ("17", "16"):
        brew_path = f"/opt/homebrew/Cellar/postgresql@{ver}"
        if os.path.isdir(brew_path):
            for entry in sorted(os.listdir(brew_path), reverse=True):
                psql = os.path.join(brew_path, entry, "bin", "psql")
                if os.path.isfile(psql):
                    return psql
    return ""


def _check_pgvector(psql: str) -> bool:
    """Check if pgvector extension is available."""
    try:
        result = subprocess.run(
            [psql, "-d", "cortex", "-tAc",
             "SELECT 1 FROM pg_available_extensions WHERE name='vector'"],
            capture_output=True, text=True, timeout=5,
        )
        return result.stdout.strip() == "1"
    except Exception:
        return False


def check_dependencies() -> dict:
    """Check all required dependencies. Returns {name: path_or_status}."""
    status = {}

    # macOS
    import platform
    status["macos"] = platform.system() == "Darwin"

    # Python 3.12+
    status["python"] = _check_python()

    # uv
    status["uv"] = shutil.which("uv") or ""

    # PostgreSQL
    status["psql"] = _check_postgres()

    # pgvector (only if psql found)
    if status["psql"]:
        status["pgvector"] = _check_pgvector(status["psql"])
    else:
        status["pgvector"] = False

    # git
    status["git"] = shutil.which("git") or ""

    return status


def print_dependency_report(status: dict) -> list[str]:
    """Print status and return list of missing items."""
    missing = []
    labels = {
        "macos": "macOS",
        "python": "Python 3.12+",
        "uv": "uv (package manager)",
        "psql": "PostgreSQL 16+",
        "pgvector": "pgvector extension",
        "git": "git",
    }
    install_hints = {
        "python": "brew install python@3.14",
        "uv": "curl -LsSf https://astral.sh/uv/install.sh | sh",
        "psql": "brew install postgresql@17",
        "pgvector": "brew install pgvector",
        "git": "xcode-select --install",
    }

    print("\n=== Dependency Check ===\n")
    for key, label in labels.items():
        val = status.get(key)
        if val:
            print(f"  [ok] {label}: {val}")
        else:
            print(f"  [!!] {label}: NOT FOUND")
            if key in install_hints:
                print(f"       Install: {install_hints[key]}")
            missing.append(key)

    return missing


def clone_or_update_repo() -> Path:
    """Clone Cortex repo or pull latest if it exists."""
    if CORTEX_DIR.is_dir() and (CORTEX_DIR / ".git").is_dir():
        print(f"\n=== Updating existing repo at {CORTEX_DIR} ===")
        _run(["git", "pull", "origin", "main"], cwd=CORTEX_DIR)
    else:
        print(f"\n=== Cloning Cortex to {CORTEX_DIR} ===")
        CORTEX_DIR.parent.mkdir(parents=True, exist_ok=True)
        _run(["git", "clone", CORTEX_REPO, str(CORTEX_DIR)])
    return CORTEX_DIR


def setup_venv(cortex_dir: Path, python: str) -> None:
    """Create venv and install deps via make dev."""
    print("\n=== Setting up virtual environment ===")
    if _cmd_exists("uv"):
        _run(["uv", "venv", ".venv", "--python", python], cwd=cortex_dir)
        _run(["make", "dev"], cwd=cortex_dir)
    else:
        _run([python, "-m", "venv", ".venv"], cwd=cortex_dir)
        _run(["make", "dev"], cwd=cortex_dir)


def run_migrations(cortex_dir: Path, psql: str) -> None:
    """Run all SQL migrations in order."""
    migrations_dir = cortex_dir / "migrations"
    if not migrations_dir.is_dir():
        print("  No migrations directory found, skipping.")
        return

    print("\n=== Running migrations ===")
    sql_files = sorted(migrations_dir.glob("*.sql"))
    for f in sql_files:
        print(f"  Applying {f.name}...")
        try:
            _run([psql, "-d", "cortex", "-f", str(f)])
        except subprocess.CalledProcessError:
            print(f"  Warning: {f.name} failed (may already be applied)")


def write_skill_config() -> None:
    """Write the skill connection config."""
    print("\n=== Writing skill config ===")
    SKILL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    config = f"""\
cortex:
  base_url: http://127.0.0.1:{DEFAULT_API_PORT}/api/v1
  workspace: default
openclaw:
  ingress_url: ""
relay:
  port: {DEFAULT_RELAY_PORT}
  enabled: false
"""
    SKILL_CONFIG_PATH.write_text(config)
    print(f"  Written to {SKILL_CONFIG_PATH}")


def main() -> int:
    print("Cortex Local Bootstrap")
    print("=" * 40)

    status = check_dependencies()
    missing = print_dependency_report(status)

    if "macos" in missing:
        print("\nThis bootstrap is designed for macOS only.")
        return 1

    critical = {"python", "psql", "git"} & set(missing)
    if critical:
        print(f"\nCritical dependencies missing: {', '.join(critical)}")
        print("Please install them and re-run bootstrap.")
        return 1

    if missing:
        print(f"\nOptional dependencies missing: {', '.join(missing)}")
        print("Continuing anyway...\n")

    cortex_dir = clone_or_update_repo()
    setup_venv(cortex_dir, status["python"])
    run_migrations(cortex_dir, status["psql"])
    write_skill_config()

    print("\n=== Bootstrap complete! ===")
    print(f"  Cortex: {cortex_dir}")
    print(f"  Config: {SKILL_CONFIG_PATH}")
    print(f"  API:    http://127.0.0.1:{DEFAULT_API_PORT}/api/v1")
    print("\nStart Cortex with:")
    print(f"  cd {cortex_dir} && source .venv/bin/activate && make serve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
