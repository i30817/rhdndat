import io
import sys
import os
import subprocess
import urllib
import shutil
import tempfile
import psutil
from urllib.parse import urlparse
from pathlib import Path
from hashlib import sha1
from functools import reduce
import re
import signal
import typer
from io import DEFAULT_BUFFER_SIZE
from typing import Optional, List
from bs4 import BeautifulSoup
from pick import pick
from colorama import Fore, init
init()

def nc_warn(string, end='\n'):
    print(string, file=sys.stderr, end=end)
def warn(string, end='\n'):
    print(Fore.YELLOW + string + Fore.RESET, file=sys.stderr, end=end)
def error(string, end='\n'):
    print(Fore.RED + string + Fore.RESET, file=sys.stderr, end=end)
def log(string, end='\n'):
    print(Fore.BLUE + string + Fore.RESET, file=sys.stderr, end=end)

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

class NonFatalError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors

class VersionFileURLError(Exception):
    def __init__(self, versionfile, url):
        super().__init__()
        self.versionfile = versionfile
        self.url = url

try:
    import xattr
except Exception as e:
    #windows will not be able to
    #but hopefully only windows
    pass

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
        raise NonFatalError('error during patching')

    return generator_function.send([])

def producer_windows(arguments, generator_function):
    ''' will append a tmp file to the end of the argument list prior to reading it and
        applying the generator function to that file. Make sure the command
        output is setup for the last argument to be a output file in the arguments
    '''
    with tempfile.SpooledTemporaryFile( max_size=psutil.virtual_memory().available-6.4e+7 ) as tmpf:
        arguments.append(tmpf)
        subprocess.run(arguments, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        #if a error occurred avoid writing bogus checksums
        if process.returncode != 0:
            raise NonFatalError('error during patching')

        tmpf.seek(0)
        next(generator_function)
        for byt in iter(lambda:f.read(DEFAULT_BUFFER_SIZE), b''):
            generator_function.send(byt)
        return generator_function.send([])

def read(x):
    return x['user.rhdndat.rom_sha1'].decode('ascii')

def needs_store(x):
    return 'user.rhdndat.rom_sha1' not in x
    
def store(x, sha1):
    x['user.rhdndat.rom_sha1'] = sha1.encode('ascii')

def getdict(elems, rf):
    #print(rf)
    d = dict()
    for x in elems:
        for r in x.find_all('rom'):
            d.setdefault(r.get('sha1'), list()).append(  x  )
    return d
        
def dictsetsum(dict1, dict2):
    for x,s in dict2.items():
        dict1[x] = dict1.setdefault(x, list()) + s
    return dict1

def mainaux(romdir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help='Directory to search for roms to rename.'),
            datdir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help='Directory to search for xml dat files to use as source of new names.'),
            force: bool = typer.Option(False, '--force', help='This option forces a recalculation and store of checksum (in unix, on windows the calculation always happens).'),
            ext: Optional[List[str]] = typer.Option(['a78', 'hdi', 'fdi', 'ngc', 'ws', 'wsc', 'pce', 'bin', 'gb', 'gba', 'gbc', 'n64', 'v64', 'z64', '3ds', 'nds', 'nes', 'lnx', 'fds', 'sfc', 'nsp', '32x', 'gg', 'sms', 'md', 'iso', 'dim', 'exe', 'bat', 'adf', 'ipf'], help='Lowercase ROM extensions to find names of. This option can be passed more than once (once per extension). Note that you can ommit this argument to get the predefined list, and also note that \'cue\' is not a valid ROM. You should always strive to use the part of the rom that has a unique identifier, for cds with multiple tracks track 1, but since we can\'t select only track 1, \'bin\'.')
            ):
    try:
        xdelta = which('xdelta3')
    except EXENotFoundError as e:
        error(f'error: rhdndat needs xdelta3 on its location, the current dir, or the OS path')
        raise typer.Abort()
    
    xmls = datdir.glob('**/*.dat')
        
    if not xmls:
        typer.echo(f'Given dat directory has no dats.')
        raise typer.Abort()
    
    dicts = map( lambda x: getdict(BeautifulSoup(open(x), 'lxml').find_all('game'), x) ,  xmls)
    combined_dict = reduce(dictsetsum, dicts, dict())
    ext = list(map( lambda s: s if s.startswith('.') else '.' + s, ext))
    default_headers = {  '.nes' : 16, '.fds' : 16,  '.lnx' : 64, '.a78' : 128  }
    renamed = set()
    for rom in (p.resolve() for p in romdir.glob('**/*') if p.suffix.lower() in ext):
        try:
            proto = rom
            if rom in renamed: #might have been already renamed from cue processing
                continue
            
            #check if needs to skip bytes
            try:
                skip = default_headers[rom.suffix.lower()]
            except KeyError as e:
                skip = 0
            generator = get_sha1(skip)
            
            #cds are handled especially to not have to bother confirming changing dozens of tracks
            chosen_cue = None
            chosen_txt = None
            for cue in rom.parent.glob('./*.cue'):
                with open(cue) as fcue:
                    txt = fcue.read()
                    if rom.name in txt: 
                        chosen_cue = cue
                        chosen_txt = txt
                        break            
            if chosen_cue:
                files = re.findall('FILE\s+"(.*)"\s+BINARY', chosen_txt)
                #instead of using a random and possibly audio track (which migth be shared by several games)
                #make sure we're using track 1 to id games, which always (?) has executables, game headers or both
                rom = rom.with_name(files[0])
            
            patch = rom.with_suffix('.rxdelta')
            #can't use xattr and the pipe version of xdelta subprocess
            if os.name == 'nt':
                if patch.is_file():
                   sha1_checksum = producer_windows([xdelta, '-d', '-s',  rom, patch],  generator)
                else:
                   sha1_checksum = file_producer(rom, generator)
            #can use xattr and the pipe version of the xdelta subprocess
            else:
                x = xattr.xattr(rom)
                should_store = force or needs_store(x)
                if patch.is_file():
                    if should_store:
                        sha1_checksum = producer_unix([xdelta, '-d', '-s',  rom, patch],  generator)
                        store(x, sha1_checksum)
                    else:
                        sha1_checksum = read(x)
                else:
                    if should_store:
                        sha1_checksum = file_producer(rom, generator)
                        store(x, sha1_checksum)
                    else:
                        sha1_checksum = read(x)
            
            if sha1_checksum not in combined_dict:
                warn(f'UNDATTED {rom.name}')
                continue
            
            if chosen_cue:
                #remove the cue elements from the running if checked once
                for f in files:
                    proto_rom = proto.with_name(f)
                    renamed.add(proto_rom)
                    if not proto_rom.is_file():
                        error(f'ERROR: cue {chosen_cue} missing track {f}')

            games = combined_dict[sha1_checksum]
            #ignore keyboard signal to not fuck up the renames of cues if using it 
            #(waits until it's out of the critical section, if you keep pressed)
            s = signal.signal(signal.SIGINT, signal.SIG_IGN)
            
            if chosen_cue:
                possibilities = ['no'] + list( map( lambda x: x.find('rom', sha1=sha1_checksum ).get('name'), games ) )
                
                default_i = len(possibilities) - 1
                if rom.name in possibilities:
                    default_i = possibilities.index(rom.name)
                    if len(possibilities) == 2:
                        continue
                if '(' not in rom.name: #likely hack! default to 'no'
                    default_i = 0
                
                choice, index = pick(possibilities,  f'RENAME {rom.name} ?', default_index=default_i)
                
                if choice != 'no':
                    game = games[index-1]
                    roms = list(game.find_all('rom'))
                    newcue = next(filter(lambda x : x.get('name').endswith('.cue'), roms))
                    roms.remove(newcue)

                    confirm = len(files) == len(roms)
                    
                    if not confirm:  
                        typer.echo(Fore.RED + f'ERROR: {chosen_cue.name} has a different number of tracks than the chosen game {choice}, skipping.' + Fore.RESET)
                        continue
                    
                    for f, r in zip(files, roms):
                        abs_oldrom = proto.with_name(f)
                        abs_newrom = proto.with_name(r.get('name'))
                        abs_oldrom.rename(abs_newrom)
                        typer.echo(Fore.GREEN + f'{abs_oldrom.name} -> {abs_newrom.name}' + Fore.RESET)
                        
                        chosen_txt = chosen_txt.replace(abs_oldrom.name, abs_newrom.name)
                        
                        #patch sibling file types that need to change name if the file changes name
                        abs_oldpatch = proto.with_name(abs_oldrom.stem+'.rxdelta')
                        if abs_oldpatch.exists():
                            abs_newpatch = proto.with_name(abs_newrom.stem+'.rxdelta')
                            abs_oldpatch.rename(abs_newpatch)
                            log(f'{abs_oldpatch.name} -> {abs_newpatch.name}')
                    
                    abs_newcue = proto.with_name(newcue.get('name'))
                    chosen_cue.rename(abs_newcue)
                    abs_newcue.write_text(chosen_txt, encoding='utf-8')
            else:
                possibilities = ['no'] + list( map( lambda x: x.find('rom', sha1=sha1_checksum ).get('name'), games ) )
                
                default_i = len(possibilities) - 1
                if rom.name in possibilities:
                    default_i = possibilities.index(rom.name)
                    if len(possibilities) == 2:
                        continue
                if '(' not in rom.name: #likely hack! default to 'no'
                    default_i = 0
                
                choice, index = pick(possibilities,  f'RENAME {rom.name} ?', default_index=default_i)
                    
                if choice != 'no':
                    game = games[index-1]
                    roms = list(game.find_all('rom'))
                    if len(roms) != 1:
                        error(f'{rom} unexpectadly has more than one file, skipping.')
                        continue
                    newrom = roms[0]
                    
                    abs_newrom = proto.with_name(newrom.get('name'))
                    rom.rename(abs_newrom)
                    typer.echo(Fore.GREEN + f'{rom.name} -> {abs_newrom.name}' + Fore.RESET)
                    
                    reset1  = rom.with_suffix('.ips')
                    reset2  = rom.with_suffix('.bps')
                    reset3  = rom.with_suffix('.ups')
                    reset4  = rom.with_suffix('.rxdelta')
                    found = False
                    if reset1.exists():
                        found = True
                        abs_newrom = abs_newrom.with_suffix('.ips')
                        reset1.rename(abs_newrom)
                        log(f'{reset1.name} -> {abs_newrom.name}')
                    elif reset2.exists():
                        found = True
                        abs_newrom = abs_newrom.with_suffix('.bps')
                        reset2.rename(abs_newrom)
                        log(f'{reset2.name} -> {abs_newrom.name}')
                    elif reset3.exists():
                        found = True
                        abs_newrom = abs_newrom.with_suffix('.ups')
                        reset3.rename(abs_newrom)
                        log(f'{reset3.name} -> {abs_newrom.name}')
                    elif reset4.exists():
                        abs_newrom = abs_newrom.with_suffix('.rxdelta')
                        reset4.rename(abs_newrom)
                        log(f'{reset4.name} -> {abs_newrom.name}')

                    #support for retroarch consecutive softpatches (not xdelta which isn't a softpatch format),
                    #until the number does not match (or 99 i guess)
                    for x in range(1, 100):
                        next1 = reset1.with_suffix('.ips{x}')
                        next2 = reset1.with_suffix('.bps{x}')
                        next3 = reset1.with_suffix('.ups{x}')
                        if next1.exists():
                            abs_newrom = abs_newrom.with_suffix('.ips{x}')
                            next1.rename(abs_newrom)
                            log(f'{next1.name} -> {abs_newrom.name}')
                        elif next2.exists():
                            abs_newrom = abs_newrom.with_suffix('.bps{x}')
                            next2.rename(abs_newrom)
                            log(f'{next2.name} -> {abs_newrom.name}')
                        elif next3.exists():
                            abs_newrom = abs_newrom.with_suffix('.ups{x}')
                            next3.rename(abs_newrom)
                            log(f'{next3.name} -> {abs_newrom.name}')
                        else:
                            break
                    
            #reneable keyboard kills
            signal.signal(signal.SIGINT, s)
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
            page = urllib.request.urlopen(url).read()
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
        except (urllib.error.URLError, AttributeError) as e:
            raise VersionFileURLError(possible_metadata, url)
    return (metadata, language)


def mainaux2(romdir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True, readable=True, resolve_path=True, help='Directory to search for versions to check.')):
    versions = romdir.glob("**/rhdndat.ver")
    try:
        for possible_metadata in versions:
            try:
               get_romhacking_data(possible_metadata)
            #non fatal errors
            except NonFatalError as e:
                warn(f'skip: {e}')
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
    typer.run(mainaux)
    return 0
            
def main():
    typer.run(mainaux2)
    return 0

if __name__ == "__main__":
    typer.run(mainaux)
