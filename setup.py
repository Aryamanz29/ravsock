from setuptools import setup, find_packages

setup(
    name='ravsock',
    version='0.1-alpha',
    packages=find_packages(),
    install_requires=[
        "numpy==1.20.1",
        "aiohttp==3.6.2",
        "async-timeout==3.0.1",
        "python-engineio==3.13.0",
        "python-socketio==4.5.1"
    ],
    dependency_links=[
        "https://github.com/ravenprotocol/ravcom.git@0.1-alpha",
        "https://github.com/ravenprotocol/ravop.git@0.1-alpha"
    ]
)
