# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/en/1.0.0/)
and this project adheres to [Semantic Versioning](http://semver.org/spec/v2.0.0.html).

## [0.5.2] - 2018-03-25
### Fixes
- Adjust depth buffer unpacking to return zero pixel value when no depth

## [0.5.1] - 2018-03-16
### Fixes
- Robustify room sampling routine (sstk dependency v0.5.1)
- Fix depth RGBA unpacking (sstk dependency v0.5.1)

### Features
- OpenAI gym wrapper allows access to underlying Simulator
- Independent setting of position, heading angle, tilt angle through `move_to` command

## [0.5.0] - 2017-12-11
### Initial beta release
