from setuptools import setup, find_packages

setup(
    name="synapse-ai",
    version="2.0.0",
    packages=find_packages(),
    install_requires=[
        "PyQt5",
        "PyQtWebEngine",
        "markdown",
        "pygments",
    ],
    entry_points={
        "console_scripts": [
            "synapse=synapse.__main__:main",
        ],
    },
)
