from setuptools import setup

setup(name='minos-sim',
      version='0.7.0',
      dependency_links=['git+https://github.com/smartscenes/socketIO-client-sstk.git@master#egg=socketIO-client-sstk-2.0.0'],
      install_requires=[
          'socketIO-client-sstk==2.0.0',
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
