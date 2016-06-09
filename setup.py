#!/usr/bin/env python

from setuptools import setup

setup(
    name='napper',
    version='0.1a1',
    description='A REST client for Python',
    license='MIT',
    url='https://github.com/epsy/napper',
    author='Yann Kaiser',
    author_email='kaiser.yann@gmail.com',
    install_requires=['aiohttp', 'chardet'],
    packages=('napper', 'napper.tests'),
    keywords=[
        'http', 'requests', 'api', 'asyncio', 'asynchronous'
        ],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.5",
        "Intended Audience :: Developers",
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "Intended Audience :: System Administrators",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP",
        ],
)
