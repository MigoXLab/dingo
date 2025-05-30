from setuptools import find_packages, setup

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()

with open("./requirements/runtime.txt", "r", encoding='utf-8') as f:
    requirements = f.readlines()

with open("./requirements/web.txt", "r", encoding='utf-8') as f:
    requirements.extend(f.readlines())

setup(
    name="dingo-python",
    version="1.7.0",
    author="Dingo",
    description="A Comprehensive Data Quality Evaluation Tool for Large Models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/DataEval/dingo",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    install_requires=[i.strip() for i in requirements],
    python_requires='>=3.10',
)
