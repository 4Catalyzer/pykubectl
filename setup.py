from setuptools import Command, setup, find_packages
import subprocess

# -----------------------------------------------------------------------------


def system(command):
    class SystemCommand(Command):
        user_options = []

        def initialize_options(self):
            pass

        def finalize_options(self):
            pass

        def run(self):
            subprocess.check_call(command, shell=True)

    return SystemCommand


# -----------------------------------------------------------------------------

setup(
    name="PyKubeCtl",
    version='0.1.3',
    description="A python bridge to kubectl",
    url='https://github.com/4Catalyzer/pykubectl',
    author="Giacomo Tagliabue",
    author_email='giacomo@gmail.com',
    license='MIT',
    classifiers=(
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ),
    keywords='kubernetes docker ci cd',
    packages=find_packages(),
    install_requires=(
        'PyYAML >= 3.11',
    ),
    cmdclass={
        'clean': system('rm -rf build dist *.egg-info'),
        'package': system('python setup.py sdist bdist_wheel'),
        'publish': system('twine upload dist/*'),
        'release': system('python setup.py clean package publish'),
    },
)
