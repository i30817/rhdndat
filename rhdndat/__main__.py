#! /usr/bin/env python3

import io
import sys
import os
import subprocess
import urllib
import shutil
import tempfile
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
from typing import Optional, List, Callable, Any
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

from collections import defaultdict
from functools import reduce
def getChecksumDict(xmls_list):
    def dictsetsum(dict1, game_tuple):
        game, origin = game_tuple
        #game['origin'] = origin #currently not needed unless you want to display the dat origin, which is ugly
        for r in game.find_all('rom'):
            dict1[r.get('sha1')].append(game)
        return dict1
    lazy_sequence = ( (x,y.name) for y in xmls_list for x in BeautifulSoup(open(y), features="xml").find_all('game'))
    return reduce(dictsetsum, lazy_sequence, defaultdict(list))

#this method might rename files.
#since we use dats to get the possible new filenames from the 'rom name' entry
#it shouldn't be possible to end up with illegal characters on windows though, unless i'm missing something.
def renamer(romdir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help='Directory to search for roms to rename.'),
            xmlpath: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=True, readable=True, resolve_path=True, help='Xml dat file or directory to search for xml dat files to use as source of new names.'),
            skip: Optional[List[Path]] = typer.Option(None, exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help='Directories to skip, can be used multiple times.'),
            ext: Optional[List[str]] = typer.Option(['a78', 'hdi', 'fdi', 'ngc', 'ws', 'wsc', 'pce', 'gb', 'gba', 'gbc', 'n64', 'v64', 'z64', '3ds', 'nds', 'nes', 'lnx', 'fds', 'sfc', 'smc', 'bs', 'nsp', '32x', 'gg', 'sms', 'md', 'iso', 'dim', 'adf', 'ipf', 'dsi', 'wad', 'cue', 'gdi', 'rvz'], help='Lowercase ROM extensions to find names of. This option can be passed more than once (once per extension). Note that you can ommit this argument to get the predefined list.'),
            force: bool = typer.Option(False, '--force', help='This option forces a recalculation and store of checksum (in unix, on windows the calculation always happens).'),
            verbose: bool = typer.Option(False, '--verbose', help='Print full paths of skipped undatted/incomplete roms.')
            ):
    """
    rom renamer
    
    rhdndat-rn renames files and patches to new .DAT¹² rom names if it can find the rom checksum in those .DAT files and memorizes the checksum of the 'original rom' as a extended attribute user.rhdndat.rom_sha1 to speed up renaming in subsequent executions (in unix, not windows).

    To find the checksum of the original file for hardpatched roms, rhdndat-rn can support a custom convention for 'revert patches'. Revert patches are a patch that you apply to a hardpatched file to get the original. These have the same name as the file and extension '.rxdelta' and are done with xdelta3. I keep them for patch updates for cd images (i don't know of any emulator that supports softpatching for those, except those that support delta chd).

    rhdndat-rn will read a xml dat file or every dat file from a directory given, and ask for renaming for every match where the name it finds is not equal to the current name. If the original rom name has square brackets or alternatively, no curved brackets, it preselects the option to 'skip', because those are hack conventions so the name is probably intentional.

    Besides rom files, files affected by renames are cues/tracks (treated especially to not ask for every track) and the softpatch types ips, bps, ups, including the new retroarch multiple softpatch convention (a number after the softpatch extension) and rxdelta.
    
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
    
    To update this program with pip installed, type:
    
    pip install --force-reinstall https://github.com/i30817/rhdndat/archive/master.zip    
    """
    try:
        xattr = None
        import xattr
    except Exception as e:
        print(e)
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
        error(f'Can\'t find xml dats in second argument.')
        raise typer.Abort()
    
    combined_dict = getChecksumDict(xmls)
    ext = list(map( lambda s: s.lower() if s.startswith('.') else '.' + s.lower(), ext))
    default_headers = {  '.nes' : 16, '.fds' : 16,  '.lnx' : 64, '.a78' : 128  }
    renamed = set()
    for rom in (p.resolve() for p in romdir.glob('**/*') if p.suffix.lower() in ext):
        if any( (excluded in rom.parents for excluded in skip) ):
            continue
        try:
            if rom in renamed: #might have been already renamed from cue processing
                continue
            
            #check if needs to skip bytes
            try:
                skipped = default_headers[rom.suffix.lower()]
            except KeyError as e:
                skipped = 0
            
            #cues/gdi are handled especially to not have to bother confirming changing dozens of tracks (xattr are stored on tracks)
            #however, this code does not handle tracks that were accidentaly renamed or unavailable. It will skip then.
            files = [ rom ] #default to share code between the cue version and single file
            index_file = None
            index_txt = None
            if rom.suffix.lower() == '.cue' or rom.suffix.lower() == '.gdi':
                with open(rom, 'r') as fcue:
                    index_txt = fcue.read()
                index_file = rom
                #instead of considering just the 'rom' file, consider also all file tracks inside cue or gdi
                files = list(map( lambda x: Path(x) if Path(x).is_absolute() else Path(rom.parent,x), re.findall('"(.*)"', index_txt)))
            
            #if using a cue as indirection, remove the other files from the check, and check if they exist before progressing
            errors = 0
            for f in files:
                if not f.is_file():
                    error(f'error: missing track {f}')
                    errors += 1
                    continue
                renamed.add(f)
            if errors > 0:
                error(f'error: please fix the {index_file.as_posix() if verbose else index_file.name} track(s)')
                continue
            
            #restore from cache or calculate and store in cache the sha1sum(s). In the case of cues/gdi, check all
            #if the file has a corresponding .rxdelta, use that as a prior patch before calculating the checksum.
            #rvz/chd, since they're container formats should not have rxdelta
            games = None
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
                    errors = 1
                    break

                if not games:
                    games = set(combined_dict[checksum])
                else:
                    games = games.intersection(combined_dict[checksum])
            if errors > 0 or not games:
                warn(f'incomplete/undatted: {rom.as_posix() if verbose else rom.name}')
                continue
            
            #turn back to list to use with the questionary api
            games = list(games)
            
            
            #Jargon: chd/rvz are 'container' files, cue/gdi/toc are 'index' files.
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
            
            #always lowercase extensions even if the current file has a different case
            suffix = rom.suffix.lower()
            will_replace_extension = suffix == '.cue' or suffix == '.gdi' or suffix == '.toc' or suffix == '.chd' or suffix == '.rvz'
            possibilities = [questionary.Choice('no')]
            for x in games:
                def find_candidate_names(n):
                    #lower is jut to be safe, i doubt that there are many dat files with uppercase extensions
                    return Path(n).suffix.lower() in ext
                names_to_show = ( y['name'] for y in x.find_all('rom', attrs={"name": find_candidate_names}) )
                if will_replace_extension:
                    names_to_show = map( lambda n: Path(n).stem + suffix,  names_to_show)
                #return the name chosen and the game when asking, if the name doesn't exist
                for name in names_to_show:
                    possibilities.append(questionary.Choice(name, value=(name,x), disabled='can\'t rename, rom exists' if Path(rom.parent, name).exists() else None))
            
            #if in the rom directory, all of the candidates (except no) already exist renaming is unnecessary (and dangerous)
            if all((x.disabled for x in possibilities[1:] )):
                continue
            
            custom_style = Style([
                ('answer', 'fg:green bold'),
            ])
            choice = questionary.select(f'rename {rom.name} ?', possibilities, style=custom_style, qmark='', default=possibilities[0]).ask()
            if choice == None: #user ctrl+c
                raise typer.Exit(code=1)
            if choice != 'no':
                #ignore keyboard signal to not fuck up the renames of cues if using it 
                #(waits until it's out of the critical section, if you keep pressed)
                def handler(signum, frame):
                    print('CTRL-C ignored while renaming files')
                previous_signal = signal.signal(signal.SIGINT,handler)
                try:
                    new_name, game = choice
                    if index_file:
                        roms_json = game.find_all('rom') #ordered by track order, just like the cue parsing
                        roms_json.pop(0) #first is the index file, discard it since we're not using the name
                        if len(files) != len(roms_json):
                            error(f'error: {index_file.name} has a different number of tracks than the chosen game {new_name}, skipping.')
                            continue
                        
                        #rename tracks
                        for oldrom, r_json in zip(files, roms_json):
                            newrom = oldrom.with_name(r_json.get('name'))
                            oldrom.rename(newrom)
                            ok(f'{oldrom.name} -> {newrom.name}')
                            #replace the 'last part' of a filename in the same dir - this way it doesn't matter if the original was absolute or relative in the cue.
                            index_txt = index_txt.replace(oldrom.name, newrom.name)
                            
                            #patch sibling file types that need to change name if the file changes name
                            oldpatch = oldrom.with_name(oldrom.stem+'.rxdelta')
                            if oldpatch.exists():
                                newpatch = oldrom.with_name(newrom.stem+'.rxdelta')
                                oldpatch.rename(newpatch)
                                log(f'{oldpatch.name} -> {newpatch.name}')
                        
                        #rename and rewrite index file
                        newcue = index_file.with_name(new_name)
                        index_file.rename(newcue)
                        newcue.write_text(index_txt, encoding='utf-8')
                        ok(f'{index_file.name} -> {newcue.name}')
                        
                        #rename sbi if it exists
                        sbi = index_file.with_suffix('.sbi')
                        if sbi.exists():
                            newsbi = newcue.with_suffix('.sbi')
                            sbi.rename(newsbi)
                            log(f'{sbi.name} -> {newsbi.name}')
                    else:
                        newrom = rom.with_name(new_name)
                        rom.rename(newrom)
                        ok(f'{rom.name} -> {newrom.name}')
                        
                        #It's a user error for patches of different type and same number to exist.
                        softpatches = [ r for r in [ rom.with_suffix('.ips'), rom.with_suffix('.bps'), rom.with_suffix('.ups') ] if r.exists() ]
                        if len(softpatches)>1:
                            warn(f'warning: more than one softpatch format exists for this rom {softpatches}')
                        #custom hardpatch removal xdelta, subchannel data, palette nes emulator file
                        others = [ r for r in [ rom.with_suffix('.rxdelta'), rom.with_suffix('.sbi'), rom.with_suffix('.pal') ] if r.exists() ]
                        for p in chain(softpatches,others):
                            newrom = newrom.with_suffix(p.suffix)
                            p.rename(newrom)
                            log(f'{p.name} -> {newrom.name}')
                        #support for retroarch consecutive softpatches (not xdelta which isn't a softpatch format),
                        #until the number does not match.
                        for x in range(1, 100):
                            softpatches = [ r for r in [ rom.with_suffix(f'.ips{x}'), rom.with_suffix(f'.bps{x}'), rom.with_suffix(f'.ups{x}') ] if r.exists() ]
                            if not softpatches:
                                break
                            if len(softpatches)>1:
                                warn(f'warning: more than one softpatch format exists for this rom {softpatches}')
                            for softpatch in softpatches:
                                newrom = newrom.with_suffix(softpatch.suffix)
                                next1.rename(newrom)
                                log(f'{softpatch.name} -> {newrom.name}')
                finally:
                    #reneable keyboard kills
                    if previous_signal:
                        signal.signal(signal.SIGINT, previous_signal)
        except PatchingError as e:
            error(f'error: possible corruption or replacement of rom file without recreating rxdelta')
            error(f' file: {rom.name}')
            error(f' path: {rom.parent.as_uri()}')
            continue
        except KeyError as e:
            continue #not a rom

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
                warn(f'warn: {language}->{tmp} : language should not have changed twice with patches from romhacking.net')
                p = Path(os.path.dirname(possible_metadata)).as_uri()
                f = Path(possible_metadata).as_uri()
                warn(f' path:  {p}')
                warn(f' file:  {f}')
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
                warn(f'warn: local \'{version}\' != upstream \'{remote_version}\' versions')
                warn(f' patch: {url}')
                warn(f' path:  {possible_metadata.parent.as_uri()}')
        except (URLError, AttributeError) as e:
            raise VersionFileURLError(possible_metadata, url)
    return (metadata, language)


def versioncheck(romdir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help='Directory to search for versions to check.'),
    quiet: bool = typer.Option(False, '--quiet', help='Don\'t show the directory of the each checked rhdndat.ver file.')
    ):
    """
    romhacking.net update checker
    
    rhdndat finds rhdndat.ver files to check for romhacking.net updates

    A version file is named rhdndat.ver and has a version number line followed by a romhacking.net url line, repeated. These correspond to each hack or translation. To check for needed updates to version file, if any patch version in the file does not match the version on the romhacking.net patch page, it presents a warning.

    To update this program with pip installed, type:
    
    pip install --force-reinstall https://github.com/i30817/rhdndat/archive/master.zip    
    """
    
    versions = romdir.glob("**/rhdndat.ver")
    try:
        for possible_metadata in versions:
            if not quiet:
                log(f'check: {possible_metadata.parent}') 
            try:
                get_romhacking_data(possible_metadata)
            except RHDNTRomRemovedError as e:
                warn(f'skip: romhacking.net deleted patch, check reason and delete last version from dat if bad')
                warn(f' patch: {e.url}')
                warn(f' path:  {e.versionfile.parent.as_uri()}')
    #fatal errors
    except VersionFileURLError as e:
        error(f'error: version file url connection failure')
        error(f' file: {Path(e.versionfile).as_uri()}')
        error(f' url:  {e.url}')
        raise typer.Abort()
    except VersionFileSyntaxError as e:
        error(f'error: version files repeat two lines, a version string and a romhacking url')
        error(f' file: {Path(e.versionfile).as_uri()}')
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

