from setuptools import setup, find_packages

setup(
    name="mindroom",
    version="0.0.0",
    description="A universal interface for AI agents with persistent memory, where every conversation has a home.",
    long_description="A universal interface for AI agents with persistent memory, where every conversation has a home.",
    author="Bas Nijholt",
    author_email="bas@nijho.lt",
    url="https://github.com/basnijholt/mindroom",
    packages=find_packages(),
    install_requires=[],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
)
