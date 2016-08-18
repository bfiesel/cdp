from setuptools import find_packages, setup
print find_packages(exclude=["*.test", "*.test.*", "test.*", "test"])
print '-----------'
print find_packages()
setup(
    name="CDP",
    version="0.1a",
    author="Zeshawn Shaheen",
    author_email="shaheen2@llnl.gov",
    description="Framework for creating climate diagnostics.",
    packages=find_packages(exclude=["*.test", "*.test.*", "test.*", "test"]),
    include_package_data=True
)
