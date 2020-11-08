from setuptools import find_packages, setup

setup(
    name="async-url-getter",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    install_requires=[
        "aiohttp==3.7.2",
        "click==7.1.2",
        "click-pathlib==2020.3.13.0",
    ],
)
