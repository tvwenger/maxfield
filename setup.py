from setuptools import setup

setup(
    name='maxfield',
    version='4.0',
    description='Ingress Maxfield: An Ingress Linking and Fielding Strategy Generator',
    author='Trey V. Wenger',
    author_email='tvwenger@gmail.com',
    packages=['maxfield'],
    install_requires=['numpy', 'networkx', 'scipy', 'ortools', 'protobuf==3.19.5',
                      'matplotlib', 'imageio', 'pygifsicle'],
    scripts=['bin/maxfield-plan'],
)
