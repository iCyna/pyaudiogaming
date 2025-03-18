from setuptools import setup, find_packages

setup(
    name="pyaudiogaming",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pygame",
        "cryptography",
        "hashlib",
        "libloader",
        "wxPython",
        "enum34",
        "pywin32",
        "nuitka",
        "requests",
    ],
    author="iCyna",
    author_email="phucnggo29@gmail.com",
    description="A toolkit for audio-based games in Python",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/iCyna/pyaudiogaming",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
