romhacking.net_ update checker and rom renamer
==============================================

.. _romhacking.net: http://www.romhacking.net


**rhdndat** finds ``rhdndat.ver`` files to check for romhacking.net updates

A version file is named ``rhdndat.ver`` and has a version number line followed by a romhacking.net url line, repeated. These correspond to each hack or translation. To check for needed updates to version file, if any patch version in the file does not match the version on the romhacking.net patch page, it presents a warning.

**rhdndat-rn** renames files and patches to new .DAT [1]_ [2]_ rom names if it can find the rom checksum in those .DAT files and memorizes the checksum of the 'original rom' as a extended attribute ``user.rhdndat.rom_sha1`` to speed up renaming in subsequent executions (in unix, not windows).

To find the checksum of the original file for hardpatched roms, rhdndat-rn can support a custom convention for 'revert patches'. Revert patches are a patch that you apply to a hardpatched file to get the original. These have the same name as the file and extension '.rxdelta' and are done with xdelta3. I keep them for patch updates for cd images (i don't know of any emulator that supports softpatching for those, except those that support delta chd).

rhdndat-rn will read a xml dat file or every dat file from a directory given, and ask for renaming for every match where the rom filename is not equal to the dat name proposed. It will skip the question if all the names proposed already exist in the rom directory, and not allow a rename to a name that is existing file in the rom directory.

Besides bare rom files, files affected by renames are compressed wii/gamecube .rvz files, .cue/.toc/.gdi (treated especially to not ask for every track), the softpatch types .ips, .bps, .ups, including the new retroarch multiple softpatch convention (a number after the softpatch extension), .rxdelta, .pal NES color palettes, and sbi subchannel data files.

``nes fds lnx a78`` roms require headers and are hardcoded to ignore headers when calculating ``user.rhdndat.rom_sha1`` to match the no-intro dat checksums that checksum everything except the header. This is problematic for hacks, where you can 'verify' a file is the right rom, but the hack was created for a rom with another header. A solution that keeps the softpatch is tracking down the right rom, hardpatching it, and creating a softpatch from the current no-intro rom to the older patched rom. For sfc and pce ips hacks that target a headered rom I recommend ipsbehead to change the patch to target the no-header rom.

Requires xdelta3 (to process rxdelta) and dolphin-tool (to operate on rvz files) on path or the same directory.

To check for updates if you have the version files:

``rhdndat romdir``
                        check if there are any updates

To rename files if you have the dat files:

``rhdndat-rn [--force] [--ext a78 --ext nes ...] romdir xmlpath``
                        the rom extensions should be all file extensions on the files you want to rename (see below for default)

rhdndat [OPTIONS] ROMDIR
  :ROMDIR:  Directory to search for versions to check.  [required]

  --show                Show link to each checked directory.
  --install-completion  Install completion for the current shell.
  --show-completion     Show completion for the current shell, to copy it or
                        customize the installation.
  --help                Show this message and exit.


rhdndat-rn [OPTIONS] ROMDIR XMLPATH
  :ROMDIR:  Directory to search for roms to rename.  [required]
  
  :XMLPATH: Xml dat file or directory to search for xml dat files to use as source of new names.  [required]

  --skip DIRECTORY      Directory to skip, can be repeated.
  --ext TEXT            ROM extensions to find names of, can be
                        repeated. Note that you can ommit this
                        argument to get the predefined list.
                        [default: a78, hdi, fdi, ngc, ws, wsc, pce,
                        gb, gba, gbc, n64, v64, z64, 3ds, nds, nes,
                        lnx, fds, sfc, smc, bs, nsp, 32x, gg, sms,
                        md, iso, dim, adf, ipf, dsi, wad, cue, gdi,
                        toc, rvz]
  --force               Force a recalculation and store of checksum
                        (on windows the calculation always happens).
  --no-rename           Check and store checksums only.
  --verbose             Print more information about skipped roms.
  --install-completion  Install completion for the current shell.
  --show-completion     Show completion for the current shell, to copy it or
                        customize the installation.
  --help                Show this message and exit.


.. [1] `scroll down and click 'prepare' to get a collection of cartidge rom .DAT files <https://datomatic.no-intro.org/index.php?page=download&s=64&op=daily>`_.
.. [2] `download cd/dvd roms .DAT files here <http://redump.org/downloads/>`_.

Install
-------

rhdndat requires python 3.8 or later.

rhdndat may fail to execute in linux if the dir ``~/.local/bin`` to is not in the ``$PATH``.

In windows, you'll want to check the option to “Add Python to PATH” when installing python. 

The project can be installed with pip but you'll have to provide your own xdelta3 and dolphin-tool executables in the path (or current dir) for supporting rvz and rxdelta.

In linux just installing xdelta3 from the repositories is enough, in windows, placing a executable for xdelta3 named ``xdelta3.exe`` in the python install ``Scripts`` directory if you installed with the path option selected is enough.

In linux you'll have to build dolphin-tool (it's not built by dolphin-emu packages) and place it in ``~/.local/bin``, and in windows you can copy it from the dolphin install directory, rename it to ``dolphin-tool.exe`` and place it in the python install ``Scripts`` directory.


+----------------+----------------------------------------------------------------------------------------+
| Latest release | ``pip install --force-reinstall rhdndat``                                              |
+----------------+----------------------------------------------------------------------------------------+
| Current code   | ``pip install --force-reinstall https://github.com/i30817/rhdndat/archive/master.zip`` |
+----------------+----------------------------------------------------------------------------------------+

Links
-----

.. class:: tablacreditos

+-------------------------------------------------------+----------------------------------------------+
| Alcaro for helpful comments and for flips             | https://github.com/Alcaro/Flips              |
+-------------------------------------------------------+----------------------------------------------+
| romhacking.net for being awesome                      | http://www.romhacking.net/                   |
+-------------------------------------------------------+----------------------------------------------+
| Turn sfc and pce ips header patches to no-header      | https://github.com/heuripedes/ipsbehead      |
| patches                                               |                                              |
+-------------------------------------------------------+----------------------------------------------+
| Remember to rename to xdelta3 and place in path       | https://github.com/jmacd/xdelta-gpl/releases |
+-------------------------------------------------------+----------------------------------------------+
| Remember to rename to dolphin-tool and place in path, | https://dolphin-emu.org/download/            |
| linux requires build                                  |                                              |
+-------------------------------------------------------+----------------------------------------------+

`The source for this project is available here
<https://github.com/i30817/rhdndat>`_.
