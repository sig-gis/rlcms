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
            "sample_pts = rlcms.cli.sample_pts:main",
            "composite_s2 = rlcms.cli.composite_s2:main", # will be deprecated
            "composite = rlcms.cli.composite:main",
            "train_test = rlcms.cli.train_test:main",
            "RFprimitives = rlcms.cli.RFprimitives:main",
            "generate_LC = rlcms.cli.generate_LC:main",
        ]
    },
    install_requires=["earthengine-api", "pandas"],
)