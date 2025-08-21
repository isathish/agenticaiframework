from setuptools import setup, find_packages
import os
import os

setup(
    name="agentic_framework",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'jsonschema>=3.2.0',
        'pyyaml>=5.3.1',
    ],
    author="Agentic Framework Team",
    author_email="contact@agenticframework.com",
    description="A Python-based SDK for building agentic applications with lightweight, high-performance agents.",
    long_description=open('README.md', 'r', encoding='utf-8').read() if os.path.exists('README.md') else "",
    long_description_content_type="text/markdown",
    url="https://github.com/your-repo/agentic-framework",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    python_requires='>=3.6',
)
