romhacking.net_ update checker and rom renamer
==============================================

.. _romhacking.net: http://www.romhacking.net


**rhdndat** finds ``rhdndat.ver`` files to check for romhacking.net updates

A version file is named ``rhdndat.ver`` and has a version number line followed by a romhacking.net url line, repeated. These correspond to each hack or translation. To check for needed updates to version file, if any patch version in the file does not match the version on the romhacking.net patch page, it presents a warning.

**rhdndat-rn** renames files and patches to new .DAT [1]_ [2]_ rom names if it can find the rom checksum in those .DAT files and memorizes the checksum of the 'original rom' as a extended attribute ``user.rhdndat.rom_sha1`` to speed up renaming in subsequent executions (in unix, not windows).

To find the checksum of the original file for hardpatched roms, rhdndat can support a custom convention for 'revert patches'. Revert patches are a patch that you apply to a hardpatched file to get the original. These have the same name as the file and extension '.rxdelta' and are done with xdelta3. I keep them for patch updates for cd images (i don't know of any emulator that supports softpatching for those, except those that support delta chd).

rhdndat-rn will read every dat file from a directory given, and ask for renaming for every match where the name it finds is not equal to the current name. If the original rom name has square brackets or alternatively, no curved brackets, it preselects the option to 'skip', because those are hack conventions so the name is probably intentional.

Besides rom files, files affected by renames are cues/tracks (treated especially to not ask for every track) and the softpatch types ips, bps, ups, including the new retroarch multiple softpatch convention (a number after the softpatch extension) and rxdelta.

To check for updates if you have the version files:

``rhdndat romdir``
                        check if there are any updates

To rename files if you have the dat files and xdelta3 (to check for rxdelta original checksum):

``rhdndat-rn [--force] [--ext...] romdir datdir``
                        the list of rom extensions should be a list of all bare file types used on your dats, the default list is:
                        ``a78 hdi fdi ngc ws wsc pce bin gb gba gbc n64 v64 z64 3ds nds nes lnx fds sfc nsp 32x gg sms md iso dim adf ipf dsi``
                        
                        as a warning, some of these extensions are very common, so if you don't restrict the 'romdir' to places where the only
                        (for instance) bin is a cd track, you might get useless checks a lot. Calling more than once with restricted romdir and
                        less extensions is always a option if you want to avoid this. Accidental renames are unlikely, because the program will
                        only ask to rename checksum matches, you need confirmation and because the checksum is unlikely to have collisions.
                        
                        Certain extensions are also hardcoded to remove a header when calculating ``user.rhdndat.rom_sha1`` to match the dat checksum.
                        There is no alternative since no-intro dumps with headers use this pattern, where the checksum is not the file checksums.
                        This is problematic for hacks, where you can 'verify' a file is the right rom, but the hack was created for a rom with another
                        header. A solution that keeps the softpatch is tracking down the right rom, hardpatching it, and creating a softpatch from the
                        current no-intro rom to the older patched rom. This is especially a problem for nes dumps, which don't work without the header.
                        For sfc and pce ips hacks that target a headered rom I recommend ipsbehead to change the patch to target the no-header rom.

Requires xdelta3 (to process rxdelta) and dolphin-tool (to operate on rvz files) on path or the same directory.

Usage: **rhdndat** [OPTIONS] **ROMDIR**

Arguments:
  ROMDIR  Directory to search for versions to check.  [required]

Options:
  --install-completion  Install completion for the current shell.
  --show-completion     Show completion for the current shell, to copy it or
                        customize the installation.
  --help                Show this message and exit.


Usage: **rhdndat-rn** [OPTIONS] **ROMDIR** **DATDIR**

Arguments:
  ROMDIR  Directory to search for roms to rename.  [required]
  
  DATDIR  Directory to search for xml dat files to use as source of new names.  [required]

Options:
  --force               This option forces a recalculation and store of
                        checksum (in unix, on windows the calculation always
                        happens).
  --ext TEXT            Lowercase ROM extensions to find names of. This option
                        can be passed more than once (once per extension).
                        Note that you can ommit this argument to get the
                        predefined list. Needs dolphin-tool (from the dolphin
                        emulator) in the $PATH to check rvz files.  [default:
                        a78, hdi, fdi, ngc, ws, wsc, pce, gb, gba, gbc, n64,
                        v64, z64, 3ds, nds, nes, lnx, fds, sfc, nsp, 32x, gg,
                        sms, md, iso, dim, adf, ipf, dsi, wad, cue, gdi, rvz]
  --install-completion  Install completion for the current shell.
  --show-completion     Show completion for the current shell, to copy it or
                        customize the installation.
  --help                Show this message and exit.

.. [1] `scroll down and click 'prepare' to get a collection of cartidge rom .DAT files <https://datomatic.no-intro.org/index.php?page=download&s=64&op=daily>`_.
.. [2] `download cd/dvd roms .DAT files here <http://redump.org/downloads/>`_.

Install
-------

rhdndat requires python 3.8 or later.

rhdndat may fail to execute if your OS doesn't add the pip install dir ``~/.local/bin`` to the path.

In windows, you'll want to check the option to “Add Python to PATH” when installing python. 

The project can be installed with pip but you'll have to provide your own xdelta executable in path (or current dir) for rhdndat-rn.

In linux just installing xdelta3 from the repositories is enough, in windows, placing a executable for xdelta3 named ``xdelta3.exe`` in the python install ``Scripts`` directory if you installed with the path option selected is enough.


+---------------------+--------------------------------------------------------------------------------------------------+
| Linux               | ``pip install --force-reinstall https://github.com/i30817/rhdndat/archive/master.zip``           |
+---------------------+--------------------------------------------------------------------------------------------------+
| Windows             | ``python -m pip install --force-reinstall https://github.com/i30817/rhdndat/archive/master.zip`` |
+---------------------+--------------------------------------------------------------------------------------------------+

Credits
---------

.. class:: tablacreditos

+-------------------------------------------------------+----------------------------------------------+
| Alcaro for helpful comments and for flips             | https://github.com/Alcaro/Flips              |
+-------------------------------------------------------+----------------------------------------------+
| romhacking.net for being awesome                      | http://www.romhacking.net/                   |
+-------------------------------------------------------+----------------------------------------------+
| Turn ips header patches to no-header patches          | https://github.com/heuripedes/ipsbehead      |
+-------------------------------------------------------+----------------------------------------------+
| Remember to rename to xdelta3 and place in path       | https://github.com/jmacd/xdelta-gpl/releases |
+-------------------------------------------------------+----------------------------------------------+
| Remember to rename to dolphin-tool and place in path, | https://dolphin-emu.org/download/            |
| linux requires build                                  |                                              |
+-------------------------------------------------------+----------------------------------------------+

`The source for this project is available here
<https://github.com/i30817/rhdndat>`_.
