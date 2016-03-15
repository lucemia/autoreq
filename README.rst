auto-requirements
=================

auto format requirements file

``autoreq --in-place requirements.txt`` ``autoreq --in-place -r ./``

Release Log:
============

version 2016.3.15.3
-------------------

1. fix requirements
2. fix autoreq parsing issues, which will fail while a package name
   contains ‘.’

thanks cloverhsc report this bug
https://github.com/lucemia/autoreq/issues/4
