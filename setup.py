from setuptools import setup

setup(name='minos-sim',
      version='0.5.1',
      dependency_links=['git+https://github.com/msavva/socketIO-client-2.git@master#egg=socketIO-client-2-0.7.4'],
      install_requires=[
          'socketIO-client-2',
          'numpy',
          'scipy',
          'easydict',
          'matplotlib',
          'pygame',
          'Pillow',
          'psutil',
          'pyyaml'
      ]
      )
