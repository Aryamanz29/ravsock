from setuptools import setup, find_packages

setup(
    name="ravsock",
    version="0.2-alpha",
    packages=find_packages(),
    install_requires=[
        "tenseal==0.3.4",
        "paramiko==2.8.0",
        "numpy==1.20.3",
        "aiohttp==3.6.2",
        "python-socketio==5.4.1",
        "python-engineio==4.2.1",
        "SQLAlchemy==1.4.26",
        "redis==3.5.3",
        "SQLAlchemy_Utils==0.37.2",
        "black==21.8b0",
        "flake8==3.9.2",
    ],
)
