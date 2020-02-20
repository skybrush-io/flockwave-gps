"""Setup script for the Flockwave GPS package."""

from setuptools import setup, find_packages

requires = ["bitstring>=3.1.3", "click>=6.2"]

__version__ = None
exec(open("flockwave/gps/version.py").read())

setup(
    name="flockwave-gps",
    version=__version__,
    author=u"Tam\u00e1s Nepusz",
    author_email="tamas@collmot.com",
    packages=find_packages(exclude=["test"]),
    include_package_data=True,
    install_requires=requires,
)
