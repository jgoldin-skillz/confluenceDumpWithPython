from setuptools import setup, find_packages

setup(
    name='confluence_dump',
    version='0.0.1',
    url='https://github.com/jgoldin-skillz/confluenceDumpWithPython.git',
    packages=['confluence_dump'],
    install_requires=['beautifulsoup4', 'Pillow', 'pandoc', 'pypandoc', 'requests'],
)
