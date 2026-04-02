from setuptools import find_packages, setup

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()


def _read_requirements(path):
    with open(path, "r", encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#') and not line.startswith('-r')]


requirements = _read_requirements("./requirements/runtime.txt")

agent_requirements = _read_requirements("./requirements/agent.txt")
hhem_requirements = _read_requirements("./requirements/hhem_integration.txt")

extras_require = {
    'agent': agent_requirements,
    'hhem': hhem_requirements,
    'all': hhem_requirements + agent_requirements,
}


setup(
    name="dingo-python",
    version="2.2.2",
    author="Dingo",
    description="A Comprehensive AI Data Quality Evaluation Tool for Large Models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MigoXLab/dingo",
    packages=find_packages(),
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
