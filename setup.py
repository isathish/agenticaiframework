from setuptools import setup, find_packages

setup(
    name="agenticaiframework",
    version="1.0.26",
    author="Sathishkumar Nagarajan",
    author_email="mail@sathishkumarnagarajan.com",
    description="AgenticAI - A Python SDK for building agentic applications with advanced orchestration, monitoring, and multimodal capabilities.",
    long_description=open("README.md").read() if __import__("os").path.exists("README.md") else "",
    long_description_content_type="text/markdown",
    url="https://github.com/isathish/AgenticAI",
    packages=find_packages(),
    install_requires=[],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
