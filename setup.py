from setuptools import setup, find_packages

# Read requirements from files
def read_requirements(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        return []

setup(
    name="agenticaiframework",
    version="1.1.0",
    author="Sathishkumar Nagarajan",
    author_email="mail@sathishkumarnagarajan.com",
    description="AgenticAI - A Python SDK for building agentic applications with advanced orchestration, monitoring, and multimodal capabilities.",
    long_description=open("README.md", encoding='utf-8').read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    url="https://github.com/isathish/agenticaiframework",
    packages=find_packages(),
    install_requires=[],
    extras_require={
        'docs': read_requirements('requirements-docs.txt'),
        'all': read_requirements('requirements-docs.txt'),
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
