from setuptools import setup, find_packages


def listify(filename):
    return filter(None, open(filename, 'r').read().split('\n'))


def remove_externals(requirements):
    return filter(lambda e: not e.startswith('-e'), requirements)

setup(
    name="vumidash",
    version="0.1.0a",
    url='http://github.com/praekelt/vumi-dashboard',
    license='BSD',
    description="Utility for serving Vumi metrics to a Geckoboard dashboard.",
    long_description=open('README.rst', 'r').read(),
    author='Praekelt Foundation',
    author_email='dev@praekeltfoundation.org',
    packages=find_packages(),
    install_requires=['setuptools'] +
                     remove_externals(listify('config/requirements.pip')),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: System :: Networking',
    ],
)
