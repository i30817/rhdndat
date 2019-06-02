rhdndat: romhacking.net_ dat creator and update checker
=======================================================

.. _romhacking.net: http://www.romhacking.net


**rhdndat** finds triples ``(rom file, softpatch file, version file)`` on the same directory and creates a clrmamepro entry on stdout or file for the result of each softpatch. It can also serve as a notifier that a update is required by comparing local versions to remote romhacking.net versions.

| A softpatch filename is:
| ``rom filename - rom extension + patch extension`` or
| ``rom filename - rom extension + .reset.xdelta``

This last is a special case to recognize hardpatched roms with revert patches.

version file is simply named ``version`` and has a version number line followed by a romhacking.net url line, repeated. These correspond to each hack or translation.

If there is no patch file, but a version file exists, the extension matches, and ``-d`` is used and does not recognize the rom, the file will be assumed to be hardpatched, which can be avoided by passing ``-i``.

During normal operation, for all roms rhdndat stores extended attributes ``user.rom.md5``, ``user.rom.crc32`` and ``user.rom.sha1`` in the rom file, and these checksums refer to the 'patched' file, even if the patch is a softpatch.

This makes rhdndat faster by only checksumming again after version file modification or after using the ``-x`` option.

The intended workflow is:

``rhdnet dir romtype -t``

``<update the patches and version files here>``

``rhdnet dir romtype ...``

Requires flips (if trying to work with ips, bps) and xdelta3 (if trying to work with xdelta) on path or the same directory.

Arguments:
----------

**rhdndat** [-h] [-o **output-file**] [-o **merge-file**] [-d **xml-file**] [-i] [-x] [-t] **search-path** **rom-type**

positional arguments:
  -search-path     directory tree to search for (rom, patches and version) files

  -rom-type        extension (without dot) of roms to find patches for

optional arguments:
  -h, --help      show this help message and exit
  -o output-file  output file, if omitted writes to stdout
  -m merge-file   merge non-overridden entries from this source file
                  to override a entry, a new entry must list the same
                  romhacking urls as the older entry

  -d xml-file     normally the name is from the romhacking.net hack page,
                  but this option picks up the game names from from this
                  clrmamepro .xml and the rom checksum (including if a
                  revert patch is available)

                  this allows adding unknown roms without a patch, which
                  can't normally be added for safety, albeit with the
                  romhacking page name (the dat blacklists the false
                  unknowns, such as music tracks in cd games)

                  it's your responsibility to use a dat that matches the
                  game/set you're scanning to avoid false unknowns

  -i              don't allow unrecognized roms to be added even if the patches
                  have a romhacking.net hack page, requires -d

  -x              forces recalculation of the extended attributes even to files
                  without a version file, for if you updated a rom file outside
                  of the rhdndat system

  -t              only test version numbers against remote version,
                  works without a patch present, exclusive option

Memory Requirements
-------------------

This tool uses named FIFO files to calculate checksums when it has to patch, so not much memory is consumed. However, for patches of large roms like isos, you should make sure you're using xdelta instead of bps, because flips tries to read the whole file into memory to create or apply a patch.

Install
-------

rhdndat requires python 3.5 or later.

`The source for this project is available here
<https://github.com/i30817/rhdndat>`_.


The project can be installed on recent linux machines with pip3 by installing rhdndat from [PyPI]_ or installing latest master from [github]_ but you'll have to provide your own flips and xdelta executables in path (or current dir) for the ips, bps and xdelta support. That depends on your distribution but you can get and build them on the sites at the end of the document.


.. [PyPI] ``pip3 install --user rhdndat``
.. [github] ``pip3 install --user https://github.com/i30817/rhdndat/archive/master.zip``

rhdndat may fail to execute if your OS doesn't add the pip3 install dir ``~/.local/bin`` - in linux - to the path

Credits
---------

.. class:: tablacreditos

+-------------------------------------------------+----------------------------------------------------+
| Alcaro for helpful comments and for flips       | https://github.com/Alcaro/Flips                    |
+-------------------------------------------------+----------------------------------------------------+
| xdelta for being fast and useful                | http://xdelta.org/                                 |
+-------------------------------------------------+----------------------------------------------------+
| romhacking.net for being a awesome resource     | http://www.romhacking.net/                         |
+-------------------------------------------------+----------------------------------------------------+

