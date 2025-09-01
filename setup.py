from setuptools import setup, find_packages
setup(
    name='autoenvforge',
    version='0.1.0',
    packages=find_packages(),
    install_requires=open('requirements.txt').readlines(),
    entry_points={
        'console_scripts': [
            'autoenvforge = autoenvforge.main:cli',
        ],
    },
    author='Your Name',
    description='Auto env setup for GitHub repos',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    license='MIT',
)
