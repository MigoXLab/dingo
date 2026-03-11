import os
from setuptools import find_packages, setup

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()


def _read_requirements(path):
    with open(path, "r", encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#') and not line.startswith('-r')]


requirements = _read_requirements("./requirements/runtime.txt")
requirements.extend(_read_requirements("./requirements/web.txt"))

agent_requirements = _read_requirements("./requirements/agent.txt")
datasource_requirements = _read_requirements("./requirements/datasource.txt")

extras_require = {
    'agent': agent_requirements,
    's3': ['boto3>=1.28.43,<2.0.0', 'botocore>=1.31.43,<2.0.0'],
    'sql': ['sqlalchemy'],
    'parquet': ['pyarrow'],
    'excel': ['openpyxl', 'xlrd'],
    'huggingface': ['datasets', 'huggingface_hub'],
    'hhem': ['transformers'],
    'datasource': datasource_requirements,
    'all': datasource_requirements + agent_requirements,
}


# 获取 app 和 web-static 目录下的所有文件
def get_data_files(directory):
    paths = []
    for (path, directories, filenames) in os.walk(directory):
        for filename in filenames:
            paths.append(os.path.join('..', path, filename))
    return paths


app_files = get_data_files('app')
web_static_files = get_data_files('web-static')

setup(
    name="dingo-python",
    version="2.0.0",
    author="Dingo",
    description="A Comprehensive AI Data Quality Evaluation Tool for Large Models",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/MigoXLab/dingo",
    packages=find_packages(),
    package_data={
        '': app_files + web_static_files,
    },
    include_package_data=True,
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    install_requires=[i.strip() for i in requirements],
    extras_require=extras_require,
    python_requires='>=3.10',
)
