from setuptools import setup, find_packages

setup(
    name="synapse-ai",
    version="3.0.0",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "PyQt5",
        "PyQtWebEngine",
        "markdown",
        "pygments",
        "requests",
        "beautifulsoup4",
        "pynput",
    ],
    extras_require={
        "voice": [
            "faster-whisper",
            "sounddevice",
            "numpy",
            "edge-tts",
        ],
        "youtube": [
            "youtube-transcript-api",
        ],
        "all": [
            "faster-whisper",
            "sounddevice",
            "numpy",
            "edge-tts",
            "youtube-transcript-api",
        ],
    },
    entry_points={
        "console_scripts": [
            "synapse=synapse.__main__:main",
        ],
    },
)
