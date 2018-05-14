#!/usr/bin/python3

import argparse, sys, os, shutil, struct, signal, hashlib, itertools
import urllib.request, subprocess, tempfile, zlib, difflib
from argparse import FileType
from urllib.parse import urlparse
from tempfile import NamedTemporaryFile
from contextlib import contextmanager

from rhdndat.__init__ import *

import importlib
try:
    assert importlib.util.find_spec('bs4') is not None
    assert importlib.util.find_spec('lxml') is not None
    assert importlib.util.find_spec('pyparsing') is not None
    assert importlib.util.find_spec('colorama') is not None
except Exception as e:
    print(libraries_error, file=sys.stderr)
    sys.exit(1)

from bs4 import BeautifulSoup
from pyparsing import *
from colorama import Fore, Back, Style, init
init()

class ScriptError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors

class InternetFatalError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors


'''wrapper class for the retroarch hack dat files'''
class Hack():
    
    def __init__(self, name, description, comments, rom, size, crc, md5, sha1):
        self._name = name
        self._description = description
        self._comments = comments
        self._rom = rom
        self._size = size
        self._crc = crc
        self._md5 = md5
        self._sha1 = sha1
        self._string = None

    @classmethod
    def fromRhdnet(cls, metadata_tuples, language, name, rom, size, crc, md5, sha1):
        '''
        main name priority:
          first hack with zero translations > rom_title > last translation > first hack
          secondary name be:
          [(last)T-lang by author] for 1+ T and 0 hacks (translations are only multiple if addendums)
          [(last)T-lang by author + # Hacks] for 1+ T and 1+ hacks + 
          [(first) Hack by author] for 0 T and 1 hack
          [(first) Hack by author + # hacks] for 0 T and 1+ hack
          # is always equal to (number of translations + number of hacks -1) when it appears
        '''

        last_translation = None
        last_translation_author = None
        first_hack = None
        first_hack_author = None
        count_translations = 0
        count_hacks = 0

        #hacks have no language, translations always do
        comments = []
        description = ''
        count = 0
        for title, author, version, url in metadata_tuples:
            comments.append(url)
            if Hack.is_rhdn_translation(url):
                description += '{}{} translation by {} version ({})'.format(' + ' if count else '', language, author, version)
                count_translations = count_translations + 1
                last_translation = title
                last_translation_author = author
            elif Hack.is_rhdn_hack(url):
                description = '{}{} hack by {} version ({})'.format(' + ' if count else '', title, author, version)
                count_hacks = count_hacks + 1
                if not first_hack:
                    first_hack = title
                    first_hack_author = author
            else:
                assert False
            count += 1

        main_title = name
        if count_hacks > 0 and count_translations == 0:
            main_title = first_hack
        if not main_title:
            main_title = last_translation
        if not main_title:
            main_title = first_hack
        if not main_title:
            assert False

        cardinal_of_hacks = (count_hacks + count_translations - 1)
        if count_translations > 0 and count_hacks == 0:
            title_suffix = '[T-{} by {}]'.format(getRegionCode(language), last_translation_author)
        elif count_translations > 0 and count_hacks > 0:
            title_suffix = '[T-{} by {} + {} hacks]'.format(getRegionCode(language), last_translation_author, cardinal_of_hacks)
        elif count_translations == 0 and count_hacks == 1:
            title_suffix = '[Hack by {}]'.format(first_hack_author)
        elif count_translations == 0 and count_hacks > 0:
            title_suffix = '[Hack by {} + {} hacks]'.format(first_hack_author, cardinal_of_hacks)
        else:
            assert False

        combined_title = '{} {}'.format(main_title, title_suffix)

        return cls(combined_title, description, comments, rom, size, crc, md5, sha1)

    @staticmethod
    def is_rhdn_translation(url_str):
        return 'www.romhacking.net/translations' in url_str

    @staticmethod
    def is_rhdn_hack(url_str):
        return 'www.romhacking.net/hacks' in url_str

    @staticmethod
    def get_rhdn_path(url_str):
        try:
            url = urlparse(url_str)
            if url.netloc and url.netloc in 'www.romhacking.net':
                return url.path
        except ValueError as e: 
            return None
        return None

    @property
    def rom_extension(self):
        (_, extension) = os.path.splitext(self._rom)
        return extension.lower()

    @property
    def rhdn_paths(self):
        urls = []
        for com in self._comments:
            loc = Hack.get_rhdn_path(com)
            if loc:
                urls.append(loc)
        return urls

    def __str__(self):
        if self._string:
            return self._string
        comments = ''
        for com in self._comments:
            comments += '\n    comment "{}"'.format(com)

        self._string = '''
game (
    name "{}"
    description "{}"
    rom ( name "{}" size {} crc {} md5 {} sha1 {} ){}
)'''.format(self._name, self._description, 
            self._rom, self._size, self._crc, self._md5, self._sha1, comments)
        return self._string



def hack_entry():
    '''clrmamepro ra hacks entries parser. Keeps a string representation and a url list'''
    def always_leading_zero_in_crc(token):
        return token[0].zfill(8)

    quotes = quotedString()
    quotes.setParseAction(removeQuotes)
    size = Word(nums)
    #max and the action is to be permissive, even if no-intro isn't
    crc = Word(hexnums, max=8).setParseAction(always_leading_zero_in_crc)
    md5 = Word(alphanums, exact=32)
    sha1 = Word(alphanums, exact=40)

    rom_data   =    Suppress(Keyword('name')) + quotes.copy().setResultsName('filename') + \
                    Suppress(Keyword('size')) + size.setResultsName('size')       + \
                    Suppress(Keyword('crc'))  + crc.setResultsName('crc')         + \
                    Suppress(Keyword('md5'))  + md5.setResultsName('md5')         + \
                    Suppress(Keyword('sha1')) + sha1.setResultsName('sha1')

    comments = ZeroOrMore(Suppress(Keyword('comment')) + quotes.copy())

    a= Suppress(Keyword('name'))        + quotes.copy().setResultsName('name')        + \
       Suppress(Keyword('description')) + quotes.copy().setResultsName('description') + \
       Suppress(Keyword('rom'))                                                       + \
       nestedExpr(content=rom_data).setResultsName('rom')                             + \
       comments.setResultsName('comments')

    def replace(token):
        rom = token.rom[0] #rom is a nestedExpr
        return Hack(token.name, token.description, token.comments,
            rom.filename, rom.size, rom.crc, rom.md5, rom.sha1)

    a.setParseAction(replace)

    output = Suppress(Keyword('game')) + nestedExpr(content=a)
    return output

def hack_dat(file):
    '''clrmamepro ra hacks dat files parser. obj.header and obj.hacks'''
    quotes = quotedString()
    dat_data   = Keyword('name') + quotes + Keyword('description') + quotes
    dat_header = Keyword('clrmamepro') + nestedExpr(content=dat_data)
    header = originalTextFor(Optional(dat_header)).setResultsName('header')
    hacks = ZeroOrMore(hack_entry()).setResultsName('hacks')
    mamepro =  header + hacks
    return mamepro.parseFile(file, parseAll=True)

@contextmanager
def named_pipes(n=1):
    dirname = tempfile.mkdtemp()
    try:
        paths = [os.path.join(dirname, 'romhack_pipe' + str(i)) for i in range(n)]
        for path in paths:
            os.mkfifo(path)
        yield paths
    finally:
        shutil.rmtree(dirname)

#skip first n bytes (normally because it's a header that the dat doesn't record)
def get_crc32(skip):
    hash_crc32  = 0

    buf = yield
    buf = buf[skip:]

    while len(buf) > 0:
        hash_crc32 = zlib.crc32(buf, hash_crc32)
        buf = yield

    yield '{:08x}'.format( hash_crc32 & 0xffffffff )

def get_checksums():
    hash_md5   = hashlib.md5()
    hash_sha1  = hashlib.sha1()
    hash_crc32 = 0
    size = 0

    buf = yield

    while len(buf) > 0:
        size += len(buf)
        hash_md5.update(buf)
        hash_sha1.update(buf)
        hash_crc32 = zlib.crc32(buf, hash_crc32)
        buf = yield

    crc = '{:08x}'.format( hash_crc32 & 0xffffffff )
    md5 = hash_md5.hexdigest()
    sha1 = hash_sha1.hexdigest()

    yield (size, crc, md5, sha1)

def file_producer(source_filename, generator_function):
    BLOCKSIZE = 2 ** 20

    next(generator_function)
    with open(source_filename, 'rb') as f:
        bytes = f.read(BLOCKSIZE)
        while len(bytes) > 0:
            generator_function.send(bytes)
            bytes = f.read(BLOCKSIZE)
    return generator_function.send([])

def which(executable):
    flips = shutil.which(executable)
    if not flips:
        flips = shutil.which(executable, path=os.path.dirname(__file__))
    if not flips:
        flips = shutil.which(executable, path=os.getcwd())
    return flips

def producer(arguments, generator_function):
    ''' will append a output fifo to the end of the argument list prior to 
        applying the generator function to that fifo. Make sure the command 
        output is setup for the last argument to be a output file in the arguments
    '''
    BLOCKSIZE = 2 ** 20
    process = None
    next(generator_function)
    with named_pipes() as pipes:
        pipe = pipes[0]
        arguments.append(pipe)
        with subprocess.Popen(arguments, 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL) as process:
            with open(pipe, 'rb') as fifo:
                bytes = fifo.read(BLOCKSIZE)
                while len(bytes) > 0:
                    generator_function.send(bytes)
                    bytes = fifo.read(BLOCKSIZE)
    
    #if a error occurred avoid writing bogus checksums
    if process.returncode != 0:
        raise ScriptError('error during patching, try to remove the header if a snes rom')

    return generator_function.send([])

def patch_producer(patch, source, generator_function):
    if patch.endswith('.xdelta'):
        xdelta = which('xdelta3')
        if not xdelta:
            raise ScriptError('xdelta3 not found')
        return producer([xdelta, '-d', '-s',  source, patch], generator_function)
    else:
        flips = which('flips')
        if not flips:
            raise ScriptError('flips not found')
        return producer([flips, '--exact', '-a', patch, source], generator_function)

#version files contain sequences of two lines: a version number and a romhacking url    
def read_version_file(possible_metadata):
    hacks_list = []
    try:
        with open(possible_metadata, 'r') as file_version:
            while True:
                version = file_version.readline()
                url = file_version.readline()
                assert ( version and url ) or not ( version or url ), 'version files require (version, url) pairs'
                if not url: break
                hacks_list += [(version.strip(), url.strip())]
    except Exception as e:
        raise ScriptError('has version file, but no valid contents')
    if not hacks_list:
        raise ScriptError('has version file, but no valid contents')
    for version, url in hacks_list:
        if not (Hack.is_rhdn_translation(url) or Hack.is_rhdn_hack(url) ):
            raise ScriptError('has non romhacking urls in version file')
    return hacks_list

def get_romhacking_data(rom, possible_metadata):
    metadata = []
    language = None
    try:
        for (version, url) in read_version_file(possible_metadata):
            page = urllib.request.urlopen(url).read()
            soup = BeautifulSoup(page, 'lxml')
            info = soup.find('table', class_='entryinfo entryinfosmall').find('tbody')

            #hacks have no language
            tmp  = info.find('th', string='Language')
            tmp  = tmp and tmp.nextSibling.string
            #it's a error for a translation to have 1+ languages, whatever combination of patches there is
            if not language:
                language = tmp
            assert ( tmp == None or tmp == language ), 'language of a translation should never change with a addendum'

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
            if remote_version and remote_version != version:
              print("warn: '{}' local '{}' != upstream '{}' versions".format(rom, version, remote_version), file=sys.stderr)
        return (metadata, language)
    except Exception as e:
        raise InternetFatalError('rhdndata requires a active internet connection', e)

def get_dat_rom_name(dat, dat_crc32):
    dat_rom = dat.find('rom', crc=dat_crc32)
    if dat_rom:
        return dat_rom.parent['name']
    return None

def line_by_line_diff(a, b):
    
    def process_tag(tag, i1, i2, j1, j2):
        if tag == 'replace':
            return Fore.BLUE + matcher.b[j1:j2] + Fore.RESET
        if tag == 'delete':
            return Fore.RED + matcher.a[i1:i2] + Fore.RESET
        if tag == 'equal':
            return matcher.a[i1:i2]
        if tag == 'insert':
            return Fore.GREEN + matcher.b[j1:j2] + Fore.RESET
        assert false, "Unknown tag %r"%tag

    lines_a = a.splitlines()
    lines_b = b.splitlines()
    out = ''
    marker = ''
    for (a, b) in itertools.zip_longest(lines_a, lines_b, fillvalue=''):
        matcher = difflib.SequenceMatcher(None, a, b)
        out += marker + ''.join(process_tag(*t) for t in matcher.get_opcodes())
        marker = '\n'
    return out

def filter_hacks(hacks, merge_hacks):
    #this filters out of the old dat old hacks with a new equivalent
    #the only thing that can semi-reliably identify a duplicate is the hack urls
    #Abort 'duplicate' erasure on different file extensions for old and new
    #(this can happen easily on N64 that has different byte order rom formats)
    #Can't handle 2+ hack entries with romhacking urls but different contents
    #(imagine a author putting optional patches on the same page)
    for p_hack in hacks:
        for i, m_hack in reversed(list(enumerate(merge_hacks))):#iterate backwards for del
            if m_hack.rom_extension == p_hack.rom_extension and m_hack.rhdn_paths == p_hack.rhdn_paths:
                a = str(m_hack)
                b = str(p_hack)
                if a != b:
                    #diff works better line by line for humans. TODO ask the user?
                    diff = line_by_line_diff(a, b)
                    print('warn: merge-dat hack overriden by:{}'.format(diff), file=sys.stderr)

                del merge_hacks[i]

def write_to_file(file, hacks, merge_dat):
    if merge_dat:
        #header already turned to text on the grammar
        #may not exist and thus be a empty string
        header = merge_dat.pop(0)
        file.write( header )
        flat_list = [item for sublist in merge_dat.hacks for item in sublist]
        
        filter_hacks(hacks, flat_list)
        hacks = flat_list + hacks
    for hack in hacks:
        file.write(str(hack))
        

def make_dat(searchdir, romtype, output_file, merge_dat, dat_file, unknown_remove, test_versions_only):
    skip_bytes = 0
    dat = None
    if dat_file:
        dat = BeautifulSoup(dat_file, 'lxml')
        #needs to skip ines header. Might be needed for other dumping groups and systems?
        if dat.find('clrmamepro', header='No-Intro_NES.xml'):
            skip_bytes = 16

    patchtypes = ['.bps', '.BPS', '.ips', '.IPS', '.xdelta', '.XDELTA', '.reset.xdelta']
    romtypes   = ['.'+romtype, '.'+romtype.upper(), '.'+romtype.lower()]

    hacks = []
    for dirpath, _, files in os.walk(searchdir):
        for rom in files:

            (root, ext) = os.path.splitext(rom)
            if ext not in romtypes:
                continue

            absolute_rom  = os.path.join(dirpath,rom)
            absolute_root = os.path.join(dirpath,root)
            def rooted(x):
                return absolute_root+x
            possible_patches = map(rooted, patchtypes)

            patches = [ x for x in possible_patches if os.path.isfile(x) ]
            possible_metadata = os.path.join(dirpath,'version')

            if not os.path.isfile(possible_metadata):
                if patches: 
                    print("warn: '{}' : has patches without a version file".format(rom), file=sys.stderr)
                continue

            try:
                (metadata, language) = get_romhacking_data(rom, possible_metadata)

                if test_versions_only:
                    continue

                softpatch = True
                if not patches:
                    if unknown_remove:
                        raise ScriptError('no patches and a version file, hardpatch possible, but -i given')
                    print("warn: '{}' : no patches and a version file, assume a hardpatch without reset".format(rom), file=sys.stderr)
                    softpatch = False

                if len(patches) > 1:
                    raise ScriptError('multiple possible patches found')

                if softpatch:
                    patch = patches[0]

                #if using dat file for name, find the rom on dat
                rom_title = None
                if dat and softpatch:
                    dat_crc32 = None
                    if skip_bytes == 0 and (patch.endswith('.bps') or patch.endswith('.BPS')):
                        #bps roms have 12 bytes footers with the source, destination and patch crc32s
                        #unfortunately, this doesn't work if the dat we're working with skips headers
                        #(except for SNES headers, which is the one header bps ignores when creating/applying a patch)
                        target = None
                        with open(patch, 'rb') as p:
                            p.seek(-12, os.SEEK_END)
                            dat_crc32 = '{:08x}'.format( struct.unpack('I', p.read(4))[0] )

                        rom_title = get_dat_rom_name(dat, dat_crc32.upper())
                        if not rom_title:
                             rom_title = get_dat_rom_name(dat, dat_crc32.lower())
                    else:
                        crc32_generator = get_crc32(skip_bytes)
                        if patch.endswith('.reset.xdelta'): #it's a hardpatch
                            dat_crc32 = patch_producer(patch, absolute_rom, crc32_generator)
                        else:
                            dat_crc32 =  file_producer(absolute_rom, crc32_generator)
                        rom_title = get_dat_rom_name(dat, dat_crc32.upper())
                        if not rom_title:
                             rom_title = get_dat_rom_name(dat, dat_crc32.lower())

                    if unknown_remove and not rom_title:
                        raise ScriptError("crc32 '{}' not found in dat".format(dat_crc32))
                    elif not rom_title:
                        print("warn: '{}' : crc32 '{}' not found in dat, but not skipped".format(rom, dat_crc32), file=sys.stderr)

                #this assumes that multiple hacks were already glued into a single softpatch if there are multiple urls
                checksums_generator = get_checksums()
                #hardpatch
                if not softpatch or patch.endswith('.reset.xdelta'):
                    (size, crc, md5, sha1) = file_producer(absolute_rom, checksums_generator)
                else:
                    (size, crc, md5, sha1) = patch_producer(patch, absolute_rom, checksums_generator)
                #we don't process this now for merge-dat to work
                hack = Hack.fromRhdnet(metadata,language,rom_title,rom,size,crc,md5,sha1)
                hacks.append(hack)
            except ScriptError as e: #let the default stop execution and print on other errors
                print("skip: '{}' : {}".format(rom, e), file=sys.stderr)
                continue

    if output_file:
        #dont add a try-except, it's not clear how to capture tmp_file to delete it on error
        with NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as tmp_file:
            write_to_file(tmp_file, hacks, merge_dat)

        shutil.move(tmp_file.name, output_file.name)
    else:
        write_to_file(sys.stdout, hacks, merge_dat)


def parse_args():
    types = argparse.RawTextHelpFormatter
    parser = argparse.ArgumentParser(description=desc_with_version, formatter_class=types)
    parser.add_argument('p', metavar=('search-path'), type=str, help=desc_search)
    parser.add_argument('r', metavar=('rom-type'), type=str, help=desc_ext)
    #dont clobber file because we may read from it in -m. move tmpfile over it later
    parser.add_argument('-o', metavar=('output-file'), type=FileType('r+', encoding='utf-8'), help=desc_output)
    parser.add_argument('-m', metavar=('merge-file'), type=FileType('r', encoding='utf-8'), help=desc_merge)
    parser.add_argument('-d', metavar=('xml-file'), type=FileType('r', encoding='utf-8'), help=desc_xml)
    parser.add_argument('-i', action='store_true', help=desc_ignore)
    parser.add_argument('-t', action='store_true', help=desc_check)
    return parser.parse_args()

def main():
    flips = which('flips')
    xdelta = which('xdelta3')
    if not (flips and xdelta):
        print('error: rhdndat needs xdelta3 and flips on the path or script dir', file=sys.stderr)
        return 1

    signal.signal(signal.SIGINT, signal.SIG_DFL) # Make Ctrl+C work

    args = parse_args()

    if '.' in args.r or not os.path.isdir(args.p):
        parser.print_help()
        return 1
    else:
        if args.t:
            args.o = None
            args.m = None
            args.d = None
            args.i = False
        try:
            dat = None if not args.m else hack_dat(args.m)
            make_dat(args.p, args.r, args.o, dat, args.d, args.i, args.t)
        except ParseException as e: #fail early for parsing this to prevent data loss
            print("error: '{}' parsing clrmamepro merge dat : {}".format(args.m.name, e), file=sys.stderr)
            return 1
        except InternetFatalError as e:
            print('error: {}'.format(e), file=sys.stderr)
            return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())



