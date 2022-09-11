#! /usr/bin/env python3

import io
import sys
import os
import subprocess
import urllib
import shutil
import tempfile
import mimetypes
from urllib.parse import urlparse
from urllib.request import urlopen
from urllib.error import URLError
from pathlib import Path
from hashlib import sha1
import re
import signal
import typer
from io import DEFAULT_BUFFER_SIZE
from itertools import chain
from collections import defaultdict, OrderedDict
from functools import reduce
from typing import Optional, List
from bs4 import BeautifulSoup
import questionary
from questionary import Style
from colorama import Fore, init
init()

def warn(string, end='\n'):
    print(Fore.YELLOW + string + Fore.RESET, file=sys.stderr, end=end)
def error(string, end='\n'):
    print(Fore.RED + string + Fore.RESET, file=sys.stderr, end=end)
def log(string, end='\n'):
    print(Fore.BLUE + string + Fore.RESET, file=sys.stderr, end=end)
def ok(string, end='\n'):
    print(Fore.GREEN + string + Fore.RESET, file=sys.stderr, end=end)

class EXENotFoundError(Exception):
    def __init__(self, executable):
        super().__init__()
        self.executable = executable

class VersionFileSyntaxError(Exception):
    def __init__(self, versionfile):
        super().__init__()
        self.versionfile = versionfile

class RHDNTRomRemovedError(Exception):
    def __init__(self, versionfile, url):
        super().__init__()
        self.versionfile = versionfile
        self.url = url

class PatchingError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors

class VersionFileURLError(Exception):
    def __init__(self, versionfile, url):
        super().__init__()
        self.versionfile = versionfile
        self.url = url

class InvalidGameError(Exception):
    def __init__(self):
        super().__init__()

def which(executable):
    flips = shutil.which(executable)
    if not flips:
        flips = shutil.which(executable, path=os.path.dirname(__file__))
    if not flips:
        flips = shutil.which(executable, path=os.getcwd())
    if not flips:
        raise EXENotFoundError(executable)
    return flips

#skip first n bytes (normally because it's a header that the dat doesn't record)
def get_sha1(skip):
    hash_sha1  = sha1()

    buf = yield
    buf = buf[skip:]

    while len(buf) > 0:
        hash_sha1.update(buf)
        buf = yield

    yield hash_sha1.hexdigest()

def link(uri, label=None, parameters=None):
    '''
    Found in github, windows console and many unix consoles trick to embeed hyperlinks/uri with text
    '''
    if label is None:
        label = uri
    if parameters is None:
        parameters = ''
    # OSC 8 ; params ; URI ST <name> OSC 8 ;; ST
    escape_mask = '\033]8;{};{}\033\\{}\033]8;;\033\\'
    return escape_mask.format(parameters, uri, label)

def file_producer(source_filename, generator_function):
    next(generator_function)
    with open(source_filename, 'rb') as f:
        for byt in iter(lambda:f.read(DEFAULT_BUFFER_SIZE), b''):
            generator_function.send(byt)
    return generator_function.send([])

def producer_unix(arguments, generator_function):
    ''' will append a output fifo to the end of the argument list prior to
        applying the generator function to that fifo. Make sure the command
        output is setup for the last argument to be a output file in the arguments
    '''
    #read and patchers write to the error stream so if there is a error
    #(that corrupts the stream), it doesn't matter because the return code would
    #be non-zero anyway
    arguments.append("/dev/stderr") #not portable to windows
    next(generator_function)
    with subprocess.Popen(arguments, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE) as process:
        for byt in process.stderr:
            generator_function.send(byt)
    #if a error occurred avoid writing bogus checksums
    if process.returncode != 0:
        raise PatchingError('error during patching')

    return generator_function.send([])

def producer_windows(arguments, generator_function):
    ''' will append a tmp file to the end of the argument list prior to reading it and
        applying the generator function to that file. Make sure the command
        output is setup for the last argument to be a output file in the arguments
    '''
    #you can't even use a spooledtemporary file as a argument to a subprocess so it has to be a real
    #file. Moreover, windows is even worse and requires a tmpdir instead of a tmp file to open it twice
    
    with tempfile.TemporaryDirectory() as d:
        patched = Path(d,'rhdndat.tmp')
        arguments.append(patched)
        with subprocess.Popen(arguments, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as process:
            pass
        #if a error occurred avoid writing bogus checksums
        if process.returncode != 0:
            raise PatchingError('error during patching')

        return file_producer(patched, generator_function)

def read(x):
    return x['user.rhdndat.rom_sha1'].decode('ascii')

def needs_store(x):
    return 'user.rhdndat.rom_sha1' not in x
    
def store(x, sha1):
    x['user.rhdndat.rom_sha1'] = sha1.encode('ascii')

def getChecksumDict(xmls_list):
    def dictsetsum(dict1, game_tuple):
        game, origin = game_tuple
        game['origin'] = origin
        for r in game.find_all('rom'):
            dict1[r.get('sha1')].append(game)
        return dict1
    lazy_sequence = ( (x,y) for y in xmls_list for x in BeautifulSoup(open(y), features="xml").find_all('game'))
    return reduce(dictsetsum, lazy_sequence, defaultdict(list))

def check_and_rename(new_name, rom, index_txt, files, game):
    ''' This will check that any file that will be renamed will not overwrite a existing file then rename
    
        extra files considered for renaming for the roms: sbi +
        for index roms (cue/toc/gdi): all the track files, all rxdelta for track files (not index_files)
        for non-index roms: rxdelta, pal, ips, ups, bps files (and the numeric extensions for those last 3)
        
        Do not attempt to rename m3u files because they can and often do have different names than the original roms.
        Use instead a recreation script after renaming, like my own create_m3u : https://gist.github.com/i30817/ba37fbb2b3c6e34ff926ad833f465055
    '''
    rename_error = False
    def print_err(file):
        nonlocal rename_error
        if not rename_error:
            rename_error = True
            error(f'error: rom rename would overwrite files in directory {link(file.parent.as_uri(),"(open dir)")}')
        error(f' {file.name}')

    torename_tracks = []
    torename_main = []
    newrom = rom.with_name(new_name)
    for old, new in ( (rom, newrom), (rom.with_suffix('.sbi'), newrom.with_suffix('.sbi')) ):
        if old != new and old.exists():
            if new.exists():
                print_err(new)
            else:
                torename_main.append((old, new))
    #if it has index text, it has tracks
    if index_txt:
        roms_json = game.find_all('rom') #these invariants (first entry is indexfile) were already tested
        roms_json.pop(0)                 #remove the cue/gdi/toc since it was renamed above
        #check tracks
        for oldtrc, r_json in zip(files, roms_json):
            #oldtrc is absolute, so newtrc is too. Tracks do not use 'newrom' for the name but the dat entry
            newtrc = oldtrc.with_name(r_json.get('name'))
            for old, new in ( (oldtrc, newtrc), (oldtrc.with_suffix('.rxdelta'), newtrc.with_suffix('.rxdelta')) ):
                if old != new and old.exists():
                    if new.exists():
                        print_err(new)
                    else:
                        torename_tracks.append((old, new))
    else:
        #uglier but allows me to check for a user error
        softpatches = [ r for r in ( rom.with_suffix('.ips'), rom.with_suffix('.bps'), rom.with_suffix('.ups') ) if r.exists() ]
        mainpatches = [ r for r in ( rom.with_suffix('.rxdelta'), rom.with_suffix('.pal') ) if r.exists() ]
        if len(softpatches)>1:
            warn(f'warn: more than one active softpatch format exists for this rom {link(rom.parent.as_uri(),"(open dir)")}')
        for r in chain(mainpatches, softpatches):
            new = newrom.with_suffix(r.suffix)
            if r != new:
                if new.exists():
                    print_err(new)
                else:
                    torename_main.append((r,new))
        #support for retroarch consecutive softpatches
        #(not xdelta which isn't a softpatch format)
        #until the numbered files do not exist.
        for x in range(1, 100):
            softpatches = [ r for r in ( rom.with_suffix(f'.ips{x}'), rom.with_suffix(f'.bps{x}'), rom.with_suffix(f'.ups{x}') ) if r.exists() ]
            if not softpatches:
                break
            if len(softpatches)>1:
                warn(f'warn: more than one active softpatch format exists for this rom {link(rom.parent.as_uri(),"(open dir)")}')
            for softpatch in softpatches:
                new = newrom.with_suffix(softpatch.suffix)
                if softpatch != new:
                    if new.exists():
                        print_err(new)
                    else:
                        torename_main.append((softpatch,new))
    if rename_error:
        #don't change files if any error was posted, just move on
        return
    for old_track, new_track in torename_tracks:
        old_track.rename(new_track)
        ok(f'{old_track.name} -> {new_track.name}')
        #replace the 'last part' of a filename
        #this way it should't matter if the original
        #was absolute or relative in the cue.
        index_txt = index_txt.replace(old_track.name, new_track.name)
    if index_txt:
        #this is the cue/toc/gdi, guarded by the existence of index text,
        #that only exists when it's those. Edit it before possible renames.
        rom.write_text(index_txt, encoding='utf-8')
    for old_main, new_main in torename_main:
        old_main.rename(new_main)
        ok(f'{old_main.name} -> {new_main.name}')

def validate_dat_game(is_index_file, files, allowed_index_extensions, allowed_extensions, game):
    '''returns (list[valid_rom_names], bool tracks_need_rename)
    
        throws error if first rom is not allowed extension for index files and it's a index file
        throws error if number of tracks is different than expected number of tracks for index files
        throws error if the number of roms with allowed extensions for non-index file doesn't match exactly the number of roms or is 0
    '''
    tracks_need_renaming = False
    roms_with_extension = []
    if is_index_file:
        #use this strategy for validating implied order, check the first 'rom' is a index file
        roms_json = game.find_all('rom') #ordered by track order, just like the cue parsing
        first     = roms_json.pop(0)
        name      = first.get('name')
        if Path(name).suffix.lower() not in allowed_index_extensions:
            error(f'error: matched game first entry is not a cue/toc/gdi (entry: {name}) {link(game["origin"],"(open datfile)")}')
            raise InvalidGameError()
        #the others are just tracks
        if len(files) != len(roms_json):
            error(f'error: matched game #tracks ({len(roms_json)}) != rom #tracks ({len(files)}) (game: {game["name"]}) {link(game["origin"],"(open datfile)")}')
            raise InvalidGameError()
        for t,r in zip(files, roms_json):
            tracks_need_renaming = t.name != r['name']
            if tracks_need_renaming:
                break
        roms_with_extension = [ first ]
    else:
        #for index games, it's implied that there is only one 'game' but for non index games there might be two isos in a cd game (not for redump but others)
        #so a single rom of a allowed extension would be asked to be renamed 'in the next rom' but not if they're not on the allowed extensions.
        roms_with_extension = game.find_all('rom', attrs={"name": lambda n: Path(n).suffix.lower() in allowed_extensions})
        if not roms_with_extension or len(roms_with_extension) != len(game.find_all('rom')):
            error(f'error: matched game without all valid extensions (game: {game["name"]}) {link(game["origin"],"(open datfile)")}')
            raise InvalidGameError()
    return (roms_with_extension, tracks_need_renaming)

#this method might rename files.
#since we use dats to get the possible new filenames from the 'rom name' entry
#it shouldn't be possible to end up with illegal characters on windows though, unless i'm missing something.
def renamer(romdir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help='Directory to search for roms to rename.'),
            xmlpath: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=True, readable=True, resolve_path=True, help='Xml dat file or directory to search for xml dat files to use as source of new names.'),
            skip: Optional[List[Path]] = typer.Option(None, exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help='Directory to skip, can be repeated.'),
            ext: Optional[List[str]] = typer.Option(['a78', 'hdi', 'fdi', 'ngc', 'ws', 'wsc', 'pce', 'gb', 'gba', 'gbc', 'n64', 'v64', 'z64', '3ds', 'nds', 'nes', 'lnx', 'fds', 'sfc', 'smc', 'bs', 'nsp', '32x', 'gg', 'sms', 'md', 'iso', 'dim', 'adf', 'ipf', 'dsi', 'wad', 'cue', 'gdi', 'toc', 'rvz'], help='ROM extensions to find names of, can be repeated. Note that you can ommit this argument to get the predefined list.'),
            force: bool = typer.Option(False, '--force', help='Force a recalculation and store of checksum (on windows the calculation always happens).'),
            norename: bool = typer.Option(False, '--no-rename', help='Check and store checksums only.'),
            verbose: bool = typer.Option(False, '--verbose', help='Print more information about skipped roms.')
            ):
    """
    rom renamer
    
    rhdndat-rn renames files and patches to new .DAT¹² rom names if it can find the rom checksum in those .DAT files and memorizes the checksum of the 'original rom' as a extended attribute user.rhdndat.rom_sha1 to speed up renaming in subsequent executions (in unix, not windows).

    To find the checksum of the original file for hardpatched roms, rhdndat-rn can support a custom convention for 'revert patches'. Revert patches are a patch that you apply to a hardpatched file to get the original. These have the same name as the file and extension '.rxdelta' and are done with xdelta3. I keep them for patch updates for cd images (i don't know of any emulator that supports softpatching for those, except those that support delta chd).

    rhdndat-rn will read a xml dat file or every dat file from a directory given, and ask for renaming for every match where the rom filename is not equal to the dat name proposed. It will skip the question if all the names proposed already exist in the rom directory, and not allow a rename to a name that is existing file in the rom directory.

    Besides bare rom files, files affected by renames are compressed wii/gamecube .rvz files, .cue/.toc/.gdi (treated especially to not ask for every track), the softpatch types .ips, .bps, .ups, including the new retroarch multiple softpatch convention (a number after the softpatch extension), .rxdelta, .pal NES color palettes, and sbi subchannel data files.
    
    'nes fds lnx a78' roms require headers and are hardcoded to ignore headers when calculating 'user.rhdndat.rom_sha1' to match the no-intro dat checksums that checksum everything except the header. This is problematic for hacks, where you can 'verify' a file is the right rom, but the hack was created for a rom with another header. A solution that keeps the softpatch is tracking down the right rom, hardpatching it, and creating a softpatch from the current no-intro rom to the older patched rom. For sfc and pce ips hacks that target a headered rom I recommend ipsbehead³ to change the patch to target the no-header rom.

    Requires xdelta3⁴ (to process rxdelta) and dolphin-tool⁵ (to operate on rvz files) on path or the same directory.
    
    ¹ scroll down and click 'prepare' to get a collection of cartrige rom .DAT files
    
    https://datomatic.no-intro.org/index.php?page=download&s=64&op=daily
    
    ² download cd/dvd roms .DAT files here
    
    http://redump.org/downloads/
    
    ³ https://github.com/heuripedes/ipsbehead
    
    ⁴ in windows download xdelta3 from here and rename it 'xdelta3.exe' and place in the path, in linux install xdelta3.
    
    https://github.com/jmacd/xdelta-gpl/releases
    
    ⁵ dolphin-tool is part of the dolphin emulator. In windows rename it 'dolphin-tool.exe', in linux you have to build it from source, then place it in the path.
    
    To update this program to the latest release with pip installed, type:
    
    pip install --force-reinstall rhdndat
    """
    try:
        xattr = None
        import xattr
    except Exception as e:
        #windows will not be able to
        #but hopefully only windows
        pass
    try:
        xdelta = which('xdelta3')
    except EXENotFoundError as e:
        warn(f'warn: rhdndat-rn needs xdelta3 on its location, the current dir, or the OS path to use rxdelta files to rename hardpatched roms')
        pass
    try:
        dolphin = which('dolphin-tool')
    except EXENotFoundError as e:
        warn(f'warn: rhdndat-rn needs dolphin-tool on its location, the current dir, or the OS path to rename rvz roms')
        pass
    xmls = []
    if xmlpath.is_file():
        xmls = [xmlpath]
    elif xmlpath.is_dir():
        xmls = xmlpath.glob('**/*.dat')
    if not xmls:
        error('Can\'t find xml dats in second argument')
        raise typer.Abort()
    if romdir in skip or any( (excluded in skip for excluded in romdir.parents) ):
        error('Can\'t process any roms because ROMDIR argument is in one of the skipped directories')
        raise typer.Abort()

    combined_dict = getChecksumDict(xmls)
    ext = list(map( lambda s: s.lower() if s.startswith('.') else '.' + s.lower(), ext))
    headers = { '.nes' : 16, '.fds' : 16,  '.lnx' : 64, '.a78' : 128 }
    savedtracks = set() #saves track files to prevent them being processed twice
    sortd = { '.cue':1, '.gdi':2, '.toc':3 } #zero is falsy so it shouldn't be used for this sort trick
    for (root,dirs,dirfiles) in os.walk(romdir, topdown=True):
        #don't walk down forbidden directories, backwards delete in place for os.walk to be notified
        for i in range(len(dirs) - 1, -1, -1):
            if Path(root, dirs[i]) in skip:
                del dirs[i]
        #filter files in each directory to have only the extensions we want, sorted so index files come first
        dirfiles = [ Path(root, p).resolve() for p in dirfiles if os.path.splitext(p)[1].lower() in ext ]
        dirfiles.sort(key=lambda x: sortd.get(x.suffix.lower()) or 4)
        for rom in dirfiles:
            #skip any already processed track file
            if rom in savedtracks:
                continue
            #limit error spam
            errors = False
            #always lowercase extensions even if the current file has a different case
            suffix = rom.suffix.lower()
            #check if needs to skip bytes
            skipped = headers.get(suffix) or 0
            #cues/gdi are handled especially to not have to bother confirming changing dozens of files (xattr are stored on track files)
            files = []
            index_txt = None
            #Checking if file is binary/text has lots of false positives if you don't want to read it all (and even some if you do),
            #Some wonderswan roms are marked as 'ISO-8859 text, with very long lines (65536), with no line terminators' by unix file utility.
            if suffix in sortd:
                #for cue/gdi/toc we do want to read it all so can easily check
                try:
                    with open(rom, 'tr') as f:
                        index_txt = f.read()
                    if not index_txt: raise Exception()
                except:
                    error(f'error: cue/toc/gdi file is not text {link(rom.as_uri(),"(open cue/toc/gdi)")} {link(rom.parent.as_uri(),"(open dir)")}')
                    continue
                #instead of considering just the 'rom' file, consider also all file referenced inside cue or gdi or toc
                #since toc and cue can have a single 'file' but multiple 'tracks' this needs a ordered set
                if rom.suffix == '.gdi':
                    regex = '"(.*)"'
                else:
                    regex = 'FILE\s+"(.*)"'
                def track_constructor(st):
                    tmp = Path(st)
                    if tmp.is_absolute():
                        return tmp.resolve()
                    return Path(rom.parent, tmp).resolve()
                files = list(map( track_constructor, OrderedDict.fromkeys(re.findall(regex, index_txt)).keys() ))
                #set so that files that repeat the same filename don't show errors right away (make sure order does not matter in this loop)
                for f in set(files):
                    if not errors:
                        if f in savedtracks:
                            errors = True
                            #if for instance, you have the redump dreamcast set and put in the cues and the gdi in the same directories
                            error('error: track(s) were checked before, may be caused by multiple files using them '
                                  f'{link(rom.as_uri(),"(open cue/toc/gdi)")} {link(rom.parent.as_uri(),"(open dir)")}')
                        if not f.is_file():
                            errors = True
                            #can happen if 'multiple index files' happened and the user renamed but not only
                            error('error: missing track(s), may be caused by corrupt file, or previous rename '
                                  f'{link(rom.as_uri(),"(open cue/toc/gdi)")} {link(rom.parent.as_uri(),"(open dir)")}')
                    savedtracks.add(f)
                if errors:
                    continue
            
            if not files: #share the next loop
                files = [ rom ]
            
            games = None
            #if any xdelta operation fails while iterating the rom/tracks, warn the user and skip this possible rename
            try:
                #restore from cache or calculate and store in cache the sha1sum(s). In the case of cues/gdi, check all
                #if the file has a corresponding .rxdelta, use that as a prior patch before calculating the checksum.
                #rvz/chd, since they're container formats should not have rxdelta
                for rfile in files:
                    #do not reuse the generators
                    generator = get_sha1(skipped)
                    checksum = None
                    if rfile.suffix.lower() == '.rvz':
                        if xattr:
                            x = xattr.xattr(rfile)
                            should_store = force or needs_store(x)
                            if should_store:
                                if dolphin:
                                    process = subprocess.run( [dolphin, 'verify', '-a', 'sha1', '-i', rfile], text=True, capture_output=True)
                                    process.check_returncode()
                                    checksum = process.stdout.strip()
                                    store(x, checksum)
                            else:
                                checksum = read(x)
                        else:
                            if dolphin:
                                process = subprocess.run( [dolphin, 'verify', '-a', 'sha1', '-i', rfile], text=True, capture_output=True)
                                process.check_returncode()
                                checksum = process.stdout.strip()
                    else:
                        patch = rfile.with_suffix('.rxdelta')
                        if xattr:
                            x = xattr.xattr(rfile)
                            should_store = force or needs_store(x)
                            #warn(f'store {should_store}: {rom.name}')
                            if patch.is_file():
                                if should_store:
                                    if xdelta:
                                       checksum = producer_unix([xdelta, '-d', '-s',  rfile, patch],  generator)
                                       store(x, checksum)
                                else:
                                    checksum = read(x)
                            else:
                                if should_store:
                                    checksum = file_producer(rfile, generator)
                                    store(x, checksum)
                                else:
                                    checksum = read(x)
                        else:
                            if patch.is_file():
                                if xdelta:
                                    checksum = producer_windows([xdelta, '-d', '-s',  rfile, patch],  generator)
                            else:
                               checksum = file_producer(rfile, generator)
                    #find the games where all 'roms' checked are represented
                    #for instance, we do not want to add games that share a music track like tombraider 1 and 2
                    if not checksum or checksum not in combined_dict:
                        errors = True
                        break
                    if not games:
                        games = set(combined_dict[checksum])
                    else:
                        games = games.intersection(combined_dict[checksum])
            except PatchingError as e:
                error(f'error: rxdelta patch failed, may be caused by base rom replacement {link(rom.parent.as_uri(),"(open dir)")}')
                continue
            if errors or not games:
                warn(f'incomplete/undatted: {link(rom.parent.as_uri(),rom.name + " (open dir)")} has no match in dats {link(xmlpath.as_uri(),"(open)")}')
                continue
            if norename:
                continue
            
            #turn back to list to use with the questionary api
            games = list(games)
            
            
            #Jargon: chd/rvz are 'container' files, cue/toc/gdi are 'index' files.
            #'games' are dat entries where all the roms searched matched.
            #Neither container or index files are checked for being part of games.
            #Container files for obvious reasons, and index files to allow different
            #formats to still match the same data and the fact they embed filenames.
            #They're also the only files that never can change extension for that reason.
            
            #unfortunately here is a big difference between dat files. Some of them (redump)
            #place always one and only one 'complete' medium per 'game' (cue/bin being 1 too).
            #for others, however, i found counterexamples like one where 2 isos are in a
            #single 'game' (Legend of Heroes - Trails in the Sky - Second Chapter).
            #This makes it problematic to find the new name in that unusual case.
            
            #Instead of doing a complicated and unstable strategy to 'make it perfect'
            #simply find all the currently checked searched extensions in the 'game'
            #and display all for the user to choose. If none are found, skip them.
            #If any already exists disable them. If all are disabled skip them.
            #In the case of index or container files, additionally replace the
            #extensions found by the current one.
            
            will_replace_extension = suffix in sortd or suffix == '.chd' or suffix == '.rvz'
            possibilities = [questionary.Choice('no')]
            current_rom_was_in_dats = False
            for x in games:
                try:
                    valid_roms, tracks_need_renaming = validate_dat_game(index_txt, files, sortd, ext, x)
                except InvalidGameError:
                    continue
                names_to_show = (y['name'] for y in valid_roms)
                if will_replace_extension:
                    names_to_show = map( lambda n: Path(n).stem + suffix,  names_to_show)
                for name in names_to_show:
                    question = [('fg:green bold',name)]
                    if rom != Path(rom.parent, name):
                        disable = False
                        if Path(rom.parent, name).exists():
                            question.append(('fg:grey bold',' (destination exists)'))
                            disable = True
                        possibilities.append(questionary.Choice(question, value=(name,x), disabled=disable))
                    elif tracks_need_renaming:
                        question.append(('fg:red bold',' (current rom, tracks need rename)'))
                        possibilities.append(questionary.Choice(question, value=(name,x), disabled=False))
                    else:#need to show that the current rom is valid otherwise user will think he 'has' to rename
                        current_rom_was_in_dats = True
                        question.append(('fg:grey bold',' (current rom)'))
                        possibilities.append(questionary.Choice(question, value=(name,x), disabled=True))
            #no game was added (or some were skipped because the dat was broken),
            #without even any track renames to be done, skip
            if all((x.disabled for x in possibilities[1:])):
                if verbose and current_rom_was_in_dats:
                    log(f'log: {link(rom.parent.as_uri(),rom.name + " (open dir)")} appears to have the correct name')
                elif verbose:
                    log(f'log: {link(rom.parent.as_uri(),rom.name + " (open dir)")} any possible name already exists in the dir')
                continue
            choice = questionary.select(f'rename {"(hack?) " if "(" not in rom.name else ""}{rom.name} ?',
                                        possibilities,
                                        style=Style([('answer', 'fg:green bold')]),
                                        default=possibilities[0]).ask()
            if choice == None: #user ctrl+c
                raise typer.Exit(code=1)
            if choice != 'no':
                #ignore keyboard signal to not fuck up the renames of cues if using it
                #(waits until it's out of the critical section, if you keep pressed)
                previous_signal = signal.signal(signal.SIGINT, signal.SIG_IGN)
                try:
                    new_name, game = choice
                    check_and_rename(new_name, rom, index_txt, files, game)
                finally:
                    #reneable keyboard kills
                    if previous_signal:
                        signal.signal(signal.SIGINT, previous_signal)

def is_rhdn_translation(url_str):
    return 'www.romhacking.net/translations' in url_str

def is_rhdn_hack(url_str):
    return 'www.romhacking.net/hacks' in url_str

def read_version_file(possible_metadata):
    ''' returns list is a list of versions and urls of the used patches
    '''
    hacks_list = []
    try:
        with open(possible_metadata, 'r') as file_version:
            while True:
                version = file_version.readline()
                url = file_version.readline()
                assert ( version and url ) or ( not version and not url )
                if not url: break
                assert is_rhdn_translation(url) or is_rhdn_hack(url)
                version = version.strip()
                url = url.strip()
                hacks_list += [(version, url)]
    except Exception as e:
        raise VersionFileSyntaxError(possible_metadata)
    if not hacks_list:
        raise VersionFileSyntaxError(possible_metadata)
    return hacks_list

def get_romhacking_data(possible_metadata):
    ''' returns the tuple (metadata, language)
        metadata is a list of (title, authors_string, version, url) 1 for each hack
        language is the last language of the hacks
    '''
    metadata = []
    language = None
    version_hacks = read_version_file(possible_metadata)

    for (version, url) in version_hacks:
        try:
            page = urlopen(url).read()
            soup = BeautifulSoup(page, 'lxml')

            #removed hacks from romhacking.net can be bad news, broken or malicious hacks
            #warn the user to verify if he might have to remove the hack from the merge file
            check_removed = soup.find('div', id='main')
            if check_removed:
                check_removed = check_removed.find('div', class_='topbar', string='Error Encountered!')
                if check_removed:
                    raise RHDNTRomRemovedError(possible_metadata, url)

            info = soup.find('table', class_='entryinfo entryinfosmall').find('tbody')

            #hacks have no language and translations shouldn't change it 2+ times
            tmp  = info.find('th', string='Language')
            tmp  = tmp and tmp.nextSibling.string
            if tmp and language and tmp != language:
                warn(f'warn: {language}->{tmp} : language should not have changed twice with patches from romhacking.net {link(possible_metadata.parent.as_uri(),"(open dir)")}')
            if tmp:
                language = tmp

            authors = info.find('th', string='Released By').nextSibling
            authors_str = authors.string
            if not authors_str:
                authors = authors.findAll('a')
                authors_str = authors[0].string
                for author in authors[1:-1]:
                    authors_str += ', {}'.format(author.string)
                authors_str += ' and {}'.format(authors[-1].string)

            metadata += [(
                info.find('div').find('div').string, #main title
                authors_str,
                version, #the version we actually have
                url
            )]

            remote_version = info.find('th', string='Patch Version').nextSibling.string.strip()
            if not remote_version:
                raise VersionFileURLError(possible_metadata, url)

            if remote_version != version:
                warn(f'warn: local \'{version}\' {link(possible_metadata.parent.as_uri(),"(open dir)")} != remote \'{remote_version}\' {link(url, "(open url)")} versions')
        except (URLError, AttributeError) as e:
            raise VersionFileURLError(possible_metadata, url)
    return (metadata, language)


def versioncheck(romdir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help='Directory to search for versions to check.'),
    show: bool = typer.Option(False, '--show', help='Show link to each checked directory.')
    ):
    """
    romhacking.net update checker
    
    rhdndat finds rhdndat.ver files to check for romhacking.net updates

    A version file is named rhdndat.ver and has a version number line followed by a romhacking.net url line, repeated. These correspond to each hack or translation. To check for needed updates to version file, if any patch version in the file does not match the version on the romhacking.net patch page, it presents a warning.

    To update this program to the latest release with pip installed, type:
    
    pip install --force-reinstall rhdndat
    """
    
    versions = romdir.glob("**/rhdndat.ver")
    try:
        for possible_metadata in versions:
            if show:
                log(f'check: {link(possible_metadata.parent.as_uri(),possible_metadata.parent.name + " (open dir)")}') 
            try:
                get_romhacking_data(possible_metadata)
            except RHDNTRomRemovedError as e:
                error(f'error: romhacking.net deleted the patch {link(e.url, "(open url)")} check reason and consider deletion {link(e.versionfile.parent.as_uri(),"(open dir)")}')
    #fatal errors
    except VersionFileURLError as e:
        error(f'error: rhdndat.ver file {link(e.versionfile.as_uri(), "(open file)")} had a connection failure {link(e.url, "(open url)")}')
        raise typer.Abort()
    except VersionFileSyntaxError as e:
        error(f'error: rhdndat.ver files should repeat two lines, a version string and a romhacking url {link(e.versionfile.as_uri(), "(open file)")}')
        raise typer.Abort()

def rename():
    typer.run(renamer)

def main():
    typer.run(versioncheck)

if __name__ == "__main__":
    error('Please run rhdndat or rhdndat-rn instead of running the script directly')
    raise typer.Abort()
    


#from chd import chd_read_header, chd_open, ChdError
#from hashlib import sha1
#def chd_sha1(chdfile: Path, possible_parents: List[Path] = []):
#    '''
#    Try to extract a list of sha1 sum strings from a chd that can be used on a dat file
#    This method supports cd type chds (returns tracks sha1) and non-cd chd (returns chd sha1)
#    But delta chd without all the ancestors in the list, or not a chd returns None
#    '''
#    parents_headers = [ chd_read_header(str(parent)) for parent in possible_parents ]
#    try:
#        headersmap = { str(path.resolve(strict=True)) : header for path, header in zip(possible_parents, parents_headers) }
#        chdfile = str(chdfile.resolve(strict=True))
#        headersmap[chdfile] = chd_read_header(chdfile)
#        
#        chd = bottom_up_chd_build(chdfile, headersmap)
#        if not chd:
#            return None
#        
#        tags = [ m.tag().to_bytes(4, byteorder='big') for m in chd.metadata() ]
#        def is_cdrom(tag):
#            return tag == b'CHCD' or tag == b'CHTR' or tag == b'CHT2' or tag == b'CHGT' or tag == b'CHGD'
#        
#        if not any(map(is_cdrom, tags)):
#            return [headersmap[chdfile].sha1]
#        
#        #do sha1sum of tracks here, draw the rest of the owl
#        checksum = sha1()
#        
#        for tag in tags:
#            
#        
#        return chd
#    except (FileNotFoundError, ChdError):
#        return None

#def bottom_up_chd_build(chdfile, headers):
#    header = headers[chdfile]
#    del headers[chdfile]
#    if header.has_parent():
#        try:
#            parentfile, _ = next(filter(lambda kv: kv[1].sha1() == header.parent_sha1(), headers.items()))
#            parentchd = bottom_up_chd_build(parentfile, headers)
#            if parentchd:
#                return chd_open(chdfile, parentchd)
#            else:
#                return None
#        except StopIteration:
#            return None
#    else:
#        return chd_open(chdfile)

