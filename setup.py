import os
import re
import subprocess
from setuptools import find_packages, setup
from setuptools.command.build_py import build_py
from setuptools.command.sdist import sdist

_BUILD_INFO_RELPATH = os.path.join("dingo", "_build.py")
_BUILD_INFO_TEMPLATE = (
    '"""Build metadata, overwritten by the packaging script at release time."""\n\n'
    'GIT_SHA = "{sha}"\n'
)


def _git_short_sha(repo_dir):
    """Short commit sha of ``repo_dir`` when it is a git checkout, else None."""
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=repo_dir, capture_output=True, text=True, timeout=10, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = completed.stdout.strip()
    return sha if re.fullmatch(r"[0-9a-f]{7,40}", sha) else None


def _stamp_build_info(target_root, repo_dir=None):
    """Write the git sha into ``<target_root>/dingo/_build.py``.

    Only ever touches the build/sdist copy, never the tracked source file, so a
    build does not dirty the working tree. Without a git checkout (e.g. building
    from an sdist, which already carries the stamped file) nothing changes and
    GIT_SHA stays whatever the file holds, 'unknown' by default.
    """
    sha = _git_short_sha(repo_dir or os.path.dirname(os.path.abspath(__file__)))
    if sha is None:
        return
    target = os.path.join(target_root, _BUILD_INFO_RELPATH)
    if os.path.isfile(target):
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(_BUILD_INFO_TEMPLATE.format(sha=sha))


class _StampedBuildPy(build_py):
    def run(self):
        super().run()
        _stamp_build_info(self.build_lib)


class _StampedSdist(sdist):
    def make_release_tree(self, base_dir, files):
        super().make_release_tree(base_dir, files)
        _stamp_build_info(base_dir)


with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()


def _read_requirements(path):
    with open(path, "r", encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#') and not line.startswith('-r')]


requirements = _read_requirements("./requirements/runtime.txt")

optional_requirements = _read_requirements("./requirements/optional.txt")
agent_requirements = _read_requirements("./requirements/agent.txt")
hhem_requirements = _read_requirements("./requirements/hhem_integration.txt")
litellm_requirements = ["litellm>=1.80.0,<1.87.0"]
retrieval_requirements = _read_requirements("./requirements/retrieval.txt")
repository_requirements = _read_requirements("./requirements/repository.txt")
# lmdeploy 单独成组：它硬性要求 transformers>=4.56 并拉入大量重依赖，作为可选推理后端不并入
# optional/all，保持默认环境轻量。需要时单独 pip install dingo-python[lmdeploy]。
# （注：幻觉检测模型已从 Vectara HHEM 换为标准 T5 的 MiniCheck，不再有 transformers<4.49 上限，
#   故 lmdeploy 与幻觉检测不再存在版本冲突；此处隔离仅出于依赖体量考虑。）
lmdeploy_requirements = ["lmdeploy"]


extras_require = {
    'optional': optional_requirements,
    'agent': agent_requirements,
    'hhem': hhem_requirements,
    'litellm': litellm_requirements,
    'retrieval': retrieval_requirements,
    'repository': repository_requirements,
    'lmdeploy': lmdeploy_requirements,
    'all': (optional_requirements + hhem_requirements + agent_requirements + litellm_requirements
            + retrieval_requirements + repository_requirements),
}


setup(
    name="dingo-python",
    version="2.6.0",
    author="Dingo",
    description="A Comprehensive AI Data Quality Evaluation Tool for Large Models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MigoXLab/dingo",
    cmdclass={"build_py": _StampedBuildPy, "sdist": _StampedSdist},
    packages=find_packages(),
    package_data={"dingo.retrieval.tasks": ["*.json"]},
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    install_requires=[i.strip() for i in requirements],
    extras_require=extras_require,
    entry_points={
        'console_scripts': [
            'dingo=dingo.run.cli:main',
        ],
    },
    python_requires='>=3.10',
)
