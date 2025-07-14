import os

from setuptools import find_packages, setup

with open("README.md", "r", encoding='utf-8') as fh:
    long_description = fh.read()

with open("./requirements/runtime.txt", "r", encoding='utf-8') as f:
    requirements = f.readlines()

with open("./requirements/web.txt", "r", encoding='utf-8') as f:
    requirements.extend(f.readlines())


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
    version="1.8",
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
    python_requires='>=3.10',
)
