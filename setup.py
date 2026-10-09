from setuptools import find_packages, setup

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
    'lmdeploy': lmdeploy_requirements,
    'all': optional_requirements + hhem_requirements + agent_requirements + litellm_requirements + retrieval_requirements,
}


setup(
    name="dingo-python",
    version="2.5.0",
    author="Dingo",
    description="A Comprehensive AI Data Quality Evaluation Tool for Large Models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MigoXLab/dingo",
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
