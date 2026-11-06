"""setup.py stamps the git sha into the build copy of dingo/_build.py."""
import importlib.util
import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def setup_module():
    import setuptools

    original = setuptools.setup
    setuptools.setup = lambda **kwargs: None  # import the helpers without building
    try:
        spec = importlib.util.spec_from_file_location("dingo_setup_under_test", REPO_ROOT / "setup.py")
        module = importlib.util.module_from_spec(spec)
        cwd = os.getcwd()
        os.chdir(REPO_ROOT)  # setup.py reads README.md relative to the cwd
        try:
            spec.loader.exec_module(module)
        finally:
            os.chdir(cwd)
    finally:
        setuptools.setup = original
    return module


def _make_target(tmp_path: Path) -> Path:
    target = tmp_path / "dingo" / "_build.py"
    target.parent.mkdir()
    target.write_text('GIT_SHA = "unknown"\n', encoding="utf-8")
    return target


def test_stamp_build_info_writes_short_sha_from_git_checkout(setup_module, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "x"], cwd=repo, check=True, env=env)
    target = _make_target(tmp_path)
    setup_module._stamp_build_info(str(tmp_path), repo_dir=str(repo))
    sha = subprocess.run(["git", "rev-parse", "--short=12", "HEAD"], cwd=repo, capture_output=True,
                         text=True, check=True).stdout.strip()
    assert f'GIT_SHA = "{sha}"' in target.read_text(encoding="utf-8")


def test_stamp_build_info_keeps_unknown_outside_a_git_checkout(setup_module, tmp_path):
    target = _make_target(tmp_path)
    no_repo = tmp_path / "plain"
    no_repo.mkdir()
    setup_module._stamp_build_info(str(tmp_path), repo_dir=str(no_repo))
    assert 'GIT_SHA = "unknown"' in target.read_text(encoding="utf-8")
