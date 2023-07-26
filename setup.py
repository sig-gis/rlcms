import setuptools
from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="rlcms",
    version="0.0",
    description="Regional Land Cover Monitoring System",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sig-gis/rlcms",
    packages=setuptools.find_packages(),
    author="Kyle Woodward",
    author_email="kw.geospatial@gmail.com",
    license="GNU GPL v3.0",
    zip_safe=False,
    include_package_data=True,
    entry_points={
        "console_scripts": [
            "00sample_pts = src.00sample_pts:main",
            "01composite_s2 = src.01composite_s2:main",
            "02train_test = src.02train_test:main",
            "03RFprimitives = src.03RFprimitives:main",
            "04generate_LC = src.04generate_LC:main",
        ]
    },
    install_requires=["earthengine-api", "pandas"],
)