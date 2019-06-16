#!/usr/bin/python3

import argparse, sys, os, shutil, struct, signal, hashlib, itertools, pathlib
import urllib.request, subprocess, tempfile, zlib, difflib, io, platform
from argparse import FileType
from urllib.parse import urlparse
from tempfile import NamedTemporaryFile
from contextlib import contextmanager
from collections import Counter
from pathlib import Path
from io import DEFAULT_BUFFER_SIZE

from rhdndat.__init__ import *

import importlib
from importlib import util
try:
    assert util.find_spec('bs4') is not None
    assert util.find_spec('lxml') is not None
    assert util.find_spec('pyparsing') is not None
    assert util.find_spec('colorama') is not None
except Exception as e:
    print(libraries_error, file=sys.stderr)
    sys.exit(1)

xattr_available = False
try:
    xattr_available = importlib.util.find_spec('xattr') is not None
    import xattr
except Exception as e:
    pass

from bs4 import BeautifulSoup
from pyparsing import *
from colorama import Fore, Back, Style, init
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

class VersionFileURLError(Exception):
    def __init__(self, versionfile, url):
        super().__init__()
        self.versionfile = versionfile
        self.url = url

class UnrecognizedRomError(Exception):
    def __init__(self, crc):
        super().__init__()
        self.crc = crc

class RHDNTRomRemovedError(Exception):
    def __init__(self, url):
        super().__init__()
        self.url = url

class NonFatalError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors

'''wrapper class for the retroarch hack dat files'''
class Hack():

    def __init__(self, name, description, patches, comments, rom, size, crc, md5, sha1):
        self._name = name
        self._description = description
        self._patches = patches
        self._comments = comments
        self._rom = rom
        self._size = size
        self._crc = crc
        self._md5 = md5
        self._sha1 = sha1
        self._paths = None

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
        patches = []
        description = ''
        count = False
        for title, author, version, url in metadata_tuples:
            patches.append(url)
            if Hack.is_rhdn_translation(url):
                description += '{}{} translation by {} version ({})'.format(' + ' if count else '', language, author, version)
                count_translations = count_translations + 1
                last_translation = title
                last_translation_author = author
            elif Hack.is_rhdn_hack(url):
                description += '{}{} by {} version ({})'.format(' + ' if count else '', title, author, version)
                count_hacks = count_hacks + 1
                if not first_hack:
                    first_hack = title
                    first_hack_author = author
            else:
                assert False
            count = True

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

        return cls(combined_title, description, patches, [], rom, size, crc, md5, sha1)

    @staticmethod
    def is_rhdn_translation(url_str):
        return 'www.romhacking.net/translations' in url_str

    @staticmethod
    def is_rhdn_hack(url_str):
        return 'www.romhacking.net/hacks' in url_str

    @staticmethod
    def get_rhdn_url(url_str):
        try:
            url = urlparse(url_str)
            if url.netloc and url.netloc in 'www.romhacking.net':
                return url
        except ValueError as e:
            return None
        return None

    @property
    def rom_extension(self):
        (_, extension) = os.path.splitext(self._rom)
        return extension.lower()

    @property
    def rhdn_paths(self): #cache this
        if self._paths:
            return self._paths

        self._paths = []
        for com in self._patches:
            loc = Hack.get_rhdn_url(com)
            if loc:
                self._paths.append(loc.path)
        return self._paths

    def __str__(self):
        patches = ''
        comments = ''
        for pat in self._patches:
            patches += '\n    patch "{}"'.format(pat)
        for com in self._comments:
            comments += '\n    comment "{}"'.format(com)

        return '''
game (
    name "{}"
    description "{}"
    rom ( name "{}" size {} crc {} md5 {} sha1 {} ){}{}
)'''.format(self._name, self._description,
            self._rom, self._size, self._crc, self._md5, self._sha1, patches, comments)

def hack_entry():
    '''clrmamepro ra hacks entries parser'''
    def always_lowercase_leading_zero_in_crc(token):
        return token[0].zfill(8)

    quotes = quotedString()
    quotes.setParseAction(removeQuotes)
    size = Word(nums)
    #max and the action is to be permissive, even if no-intro isn't
    crc = Word(hexnums, max=8).setParseAction(always_lowercase_leading_zero_in_crc)
    md5 = Word(alphanums, exact=32)
    sha1 = Word(alphanums, exact=40)

    rom_data   =    Suppress(Keyword('name')) + quotes.copy().setResultsName('filename') + \
                    Suppress(Keyword('size')) + size.setResultsName('size')       + \
                    Suppress(Keyword('crc'))  + crc.setResultsName('crc')         + \
                    Suppress(Keyword('md5'))  + md5.setResultsName('md5')         + \
                    Suppress(Keyword('sha1')) + sha1.setResultsName('sha1')

    patches = ZeroOrMore(Suppress(Keyword('patch')) + quotes.copy())
    comments = ZeroOrMore(Suppress(Keyword('comment')) + quotes.copy())

    a= Suppress(Keyword('name'))        + quotes.copy().setResultsName('name')        + \
       Suppress(Keyword('description')) + quotes.copy().setResultsName('description') + \
       Suppress(Keyword('rom'))                                                       + \
       nestedExpr(content=rom_data).setResultsName('rom')                             + \
       patches.setResultsName('patches')                                              + \
       comments.setResultsName('comments')

    def replace(token):
        rom = token.rom[0] #rom is a nestedExpr
        return Hack(token.name, token.description, token.patches, token.comments,
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
    next(generator_function)
    with open(source_filename, 'rb') as f:
        for byt in iter(lambda:f.read(DEFAULT_BUFFER_SIZE), b''):
            generator_function.send(byt)
    return generator_function.send([])

def producer(arguments, generator_function):
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

def patch_producer(patch, source, generator_function):
    if patch.endswith('.xdelta'):
        xdelta = which('xdelta3')
        return producer([xdelta, '-d', '-s',  source, patch], generator_function)
    else:
        flips = which('flips')
        return producer([flips, '--exact', '-a', patch, source], generator_function)

def read_version_file(possible_metadata):
    ''' returns tuple (version_id, [(version,url])
        version_id, refers to the local version entries crc32 as a cache
        invalidation marker when the version file changed (the user edited the version file)
        the list is a list of versions and urls of the used patches
    '''
    hacks_list = []
    crc = get_crc32(0)
    next(crc)
    try:
        with open(possible_metadata, 'r') as file_version:
            while True:
                version = file_version.readline()
                url = file_version.readline()
                assert ( version and url ) or ( not version and not url )
                if not url: break
                assert Hack.is_rhdn_translation(url) or Hack.is_rhdn_hack(url)
                version = version.strip()
                url = url.strip()
                crc.send(version.encode('utf-8'))
                crc.send(url.encode('utf-8'))
                hacks_list += [(version, url)]
    except Exception as e:
        raise VersionFileSyntaxError(possible_metadata)
    if not hacks_list:
        raise VersionFileSyntaxError(possible_metadata)
    return (crc.send([]), hacks_list)

def get_romhacking_data(rom, possible_metadata):
    ''' returns the tuple (metadata, language)
        metadata is a list of (title, authors_string, version, url) 1 for each hack
        language is the last language of the hacks
    '''
    metadata = []
    language = None
    _, version_hacks = read_version_file(possible_metadata)

    for (version, url) in version_hacks:
        try:
            page = urllib.request.urlopen(url).read()
            soup = BeautifulSoup(page, 'lxml')

            #removed hacks from romhacking.net can be bad news, broken or malicious hacks
            #warn the user to verify if he might have to remove the hack from the merge file
            check_removed = soup.find('div', id='main')
            if check_removed:
                check_removed = check_removed.find('div', class_='topbar', string='RHDN Error Encountered!')
                if check_removed:
                    raise RHDNTRomRemovedError(url)

            info = soup.find('table', class_='entryinfo entryinfosmall').find('tbody')

            #hacks have no language and translations shouldn't change it 2+ times
            tmp  = info.find('th', string='Language')
            tmp  = tmp and tmp.nextSibling.string
            if tmp and language and tmp != language:
                warn('warn: {}->{} : language should not have changed twice with patches from romhacking.net'.format(language,tmp))
                p = Path(os.path.dirname(possible_metadata)).as_uri()
                f = Path(possible_metadata).as_uri()
                warn(' path:  {}'.format(p))
                warn(' file:  {}'.format(f))
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
            if remote_version and remote_version != version: #not a error to not force users to upgrade
                warn("warn: {} local '{}' != upstream '{}' versions".format(rom, version, remote_version))
                p = Path(os.path.dirname(possible_metadata)).as_uri()
                f = Path(possible_metadata).as_uri()
                warn(' patch: {}'.format(url))
                warn(' path:  {}'.format(p))
                warn(' file:  {}'.format(f))
        except urllib.error.URLError as e:
            raise VersionFileURLError(possible_metadata, url)
    return (metadata, language)

def get_dat_rom_name(dat, dat_crc32):
    upper_case = dat_crc32.upper() #argument is lowercase
    def ignorecase(crc):
        return crc == dat_crc32 or crc == upper_case

    dat_rom = dat.find('rom', crc=ignorecase)
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
    """ This filters out of the old dat old hacks with a new equivalent
        It also updates fields in other non-completely matching hacks but
        that have the same source urls.

        algorithm:
        Invariant: if it exists, a complete match is always the last change
        Invariant: two repeated runs won't show further changes

        warnings: warn on 2+ cds of the same hack need the same name on updates
        error cases:
            It's possible 2+ hacks with same romhacking urls and different optional patches
            to have their text replaced, but that case is kept to 'different extensions'
            to minimize the 'different functionality' and maximize the 'different fileformat'
            Same extension but different filenames are not touched on (for multiple discs etc)
            So this should be very rare. The change will show on diffs
    """
    diffs = {}
    delete_marker = object()

    def freeze(index, hack):
        already = diffs.get(index, None)
        if not already:
            diffs[index] = str(hack)
        return already

    def not_frozen(index):
        return diffs.get(index, None) == None

    def update(ix, x, iy, y):
        freeze(iy, y)
        merge_hacks[iy] = x
        hacks[ix] = delete_marker

    def match_one_if_available(lst, error, index, h):
        available = hacks[index] != delete_marker
        if available and len(lst) == 1:
            update(index,h,*lst[0])
        elif len(lst) > 1:
            warn(error)
            for iy,y in lst:
                warn('\u2022 ' + y._name)

    for index, h in enumerate(hacks):

        if h == delete_marker:
            continue

        candidates = [ (i,x) for i,x in enumerate(merge_hacks) if x.rhdn_paths == h.rhdn_paths ]
        if not candidates:
            continue

        if len(candidates) == 1:
            update(index, h, *candidates[0])
            continue

        count = Counter()
        def counter(ix,x,iy,y):
            count[x._rom.lower()] +=1
            count[y._rom.lower()] +=1
            return (ix,x,iy,y)

        #including current, this is the strict match for the filename equality matrix
        other_cd_hacks = [ x for x in enumerate(hacks[index:], index) if x[1]!=delete_marker and x[1].rhdn_paths == h.rhdn_paths]
        a= [ counter(ix,x,iy,y) for ix,x in other_cd_hacks for iy,y in candidates if x._rom.lower() == y._rom.lower() ] 

        #for all ._rom that match, they only match on a single pair (x,y)
        #Any hack in A (that is of the same urls and with equal romnames on hacks and merge_hacks)
        #will 'frozen' after the below branches, regardless if it matched anything or not, and hacks
        #in 'hacks' will be marked for deletion. The following operations must respect 'frozen' status
        #multi cd hacks with different names will still be added as 'new' hacks, which is problematic
        #if the crc check below doesn't catch it (ie, it's a new version)
        if len(a) > 1 and all( x[1] == 2 for x in count.most_common() ):
            log('info: updating hack as a multi-medium hack because of multiple matching filenames')
            for tuples in a:
                update(*tuples)
                log('\u2022 ' + tuples[3]._rom)
        elif len(a) > 1:
            warn('skip: you have the wrong number of hacks with the same urls+filename on either the scanned roms or the merge file')
            for ix,_,iy,y in a:
                if not freeze(iy,y):
                    hacks[ix] = delete_marker
                    warn('\u2022 ' + y._rom)

        #same hack crc -> same hack version
        matches = [ (ix,x) for ix,x in candidates if not_frozen(ix) and x._crc == h._crc ]
        error = "warn: {}, {} matching crcs {} in the merge file".format(h._name, len(matches), h._crc)
        match_one_if_available(matches, error, index, h)

        #only hack with a fileformat after 'cd' elimination -> only hack possibility
        extension = h.rom_extension
        ext = [ (ix,x) for ix,x in candidates if not_frozen(ix) and x.rom_extension == extension ]
        error = "warn: {}, {} urls+extension matches after full filename (multi-cd) filter".format(h._name, len(ext))
        match_one_if_available(ext, error, index, h)

        #non-match update for hacks with different fileformats where the
        #user only has one softpatch ready but the program can tell others apply
        #this needs to be obey frozen (ideally freeze values themselves if not frozen)
        #TODO Version could conflict (needs better parsers to fix)
        extension = h.rom_extension
        not_ext = [ (ix,x) for ix,x in candidates if not_frozen(ix) and x.rom_extension != extension]
        for i2, h2 in not_ext:
            freeze(i2, h2)
            h2._name = h._name
            h2._description = h._description
            filename_minus_extension = ''.join(h._rom.rsplit(extension))
            h2._rom = filename_minus_extension + h2.rom_extension
            for ncom in h._patches:
                if Hack.get_rhdn_url(ncom):
                    for (i, ocom) in enumerate(h2._patches):
                        if Hack.get_rhdn_url(ocom):
                            h2._patches[i] = ncom

    for i,x in reversed(list(enumerate(hacks))):
        if x == delete_marker:
            del hacks[i]

    #after if i want to allow user intervention in edits, this must be done differently
    diffs = [ line_by_line_diff(value, str(merge_hacks[key])) for key,value in diffs.items() if str(merge_hacks[key]) != value]
    if diffs:
        l = len(diffs)
        lstr = ( str(l)+' ' ) if l > 1 else ''
        lsuffix = '' if l == 1 else 's'
        warn('warn: {}merge-file hack{} overriden:'.format(lstr, lsuffix), end='')
        for value in diffs:
            nc_warn(value, end='')
        nc_warn('')

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

def checksums_strategy(patch, rom, skip_bytes):
    checksums_generator = get_checksums()
    if patch and not patch.endswith('.reset.xdelta'): #actual softpatch
        size, crc, md5, sha1 = patch_producer(patch, rom, checksums_generator)
        dat_crc32 = file_producer(rom, get_crc32(skip_bytes))
    else: #possible hardpatch (with reset or not) or just normal file of the right type
        size, crc, md5, sha1 = file_producer(rom, checksums_generator)
        if patch:
            dat_crc32 = patch_producer(patch, rom, get_crc32(skip_bytes))
        else: #normal file or hardpatch without reset
            dat_crc32 =  crc
    return dat_crc32, size, crc, md5, sha1

def all_there(x):
    return ('user.rom.size' in x
        and 'user.rom.crc32' in x
        and 'user.rom.md5' in x
        and 'user.rom.sha1' in x)
        #and 'user.rom.crc32_source' in x)

def read(x):
    size = int(x['user.rom.size'].decode('ascii'))
    crc  = x['user.rom.crc32'].decode('ascii')
    md5  = x['user.rom.md5'].decode('ascii')
    sha1 = x['user.rom.sha1'].decode('ascii')
    try:
        dat_crc32 = x['user.rom.crc32_source'].decode('ascii')
    except KeyError as _:
        dat_crc32 = crc
    return dat_crc32, size, crc, md5, sha1

def store(x, dat_crc32, size, crc, md5, sha1):
    x['user.rom.size'] = str(size).encode('ascii')
    x['user.rom.crc32'] = crc.encode('ascii')
    x['user.rom.md5'] = md5.encode('ascii')
    x['user.rom.sha1'] = sha1.encode('ascii')
    if dat_crc32 != crc:
        x['user.rom.crc32_source'] = dat_crc32.encode('ascii')


def make_dat(searchdir, romtype, output_file, merge_dat, dat_file, unknown_remove, test_versions_only, forcexattr, bailout):
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

    for dirpath, _, files in os.walk(os.path.abspath(searchdir)):
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
            metadata_exists = os.path.isfile(possible_metadata)

            try:
                if test_versions_only:
                    if metadata_exists:
                        get_romhacking_data(rom, possible_metadata)
                    continue

                #force user to fix this
                if len(patches) > 1:
                    raise NonFatalError('multiple possible patches found')

                #this assumes that multiple hacks were already glued into a single softpatch if there are multiple urls
                patch = None
                if patches:
                    patch = patches[0]

                ###find checksums of the 'final' patched file and the original if possible###
                if not xattr_available:
                    orig_crc, size, crc, md5, sha1 = checksums_strategy(patch, absolute_rom, skip_bytes)
                elif not metadata_exists:
                    x = xattr.xattr(absolute_rom)
                    if not forcexattr and all_there(x):
                        orig_crc, size, crc, md5, sha1 = read(x)
                    else:
                        orig_crc, size, crc, md5, sha1 = checksums_strategy(patch, absolute_rom, skip_bytes)
                        store(x, orig_crc, size, crc, md5, sha1)
                elif metadata_exists:
                    verX = xattr.xattr(possible_metadata)
                    version_id = read_version_file(possible_metadata)[0].encode('ascii')
                    version_match = 'user.rhdndat.version_id' in verX and verX['user.rhdndat.version_id'] == version_id
                    x = xattr.xattr(absolute_rom)

                    if not forcexattr and version_match and all_there(x):
                        orig_crc, size, crc, md5, sha1 = read(x)
                    else:
                        orig_crc, size, crc, md5, sha1 = checksums_strategy(patch, absolute_rom, skip_bytes)
                        store(x, orig_crc, size, crc, md5, sha1)
                        if not version_match:
                            verX['user.rhdndat.version_id'] = version_id
                        log('info: {} : stored checksums as extended attributes'.format(rom))

                #after xattr there is no longer any need to process files in these cases
                if bailout or not metadata_exists:
                    if not metadata_exists and patch:
                        warn("warn: {} : has patch without a version file".format(rom))
                    continue

                original_rom_title = None
                known_rom = False
                if dat:
                    #if the file was irreversibly patched or unknown this will fail
                    known_rom = get_dat_rom_name(dat, crc)
                    #the original rom title
                    original_rom_title = get_dat_rom_name(dat, orig_crc)

                    if unknown_remove and not original_rom_title:
                        raise UnrecognizedRomError(orig_crc)

                #Files can be in same directory, part of the same game and with
                #the same extension, and not patched at all (cd music tracks), filter
                if patch or (dat and not known_rom):
                    if not patch and not known_rom:
                        log("info: {} : no patch and crc32 {} not found in dat, assume a hardpatch".format(rom, crc))
                    metadata, language = get_romhacking_data(rom, possible_metadata)
                    #we don't process this now for merge-dat to work
                    hack = Hack.fromRhdnet(metadata,language,original_rom_title,rom,size,crc,md5,sha1)
                    hacks.append(hack)
            except UnrecognizedRomError as e:
                warn('skip: {} : crc {} not in dat file'.format(rom, e.crc))
                continue
            except RHDNTRomRemovedError as e:
                warn('skip: {} : romhacking.net deleted patch, check reason and delete last version from dat if bad'.format(rom))
                warn(' patch: {}'.format(e.url))
                continue
            except NonFatalError as e:
                warn('skip: {} : {}'.format(rom, e))
                warn(' path: {}'.format(Path(dirpath).as_uri()))
                continue

    if output_file:
        with NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as tmp_file:
            write_to_file(tmp_file, hacks, merge_dat)
        shutil.move(tmp_file.name, output_file.name)
    else:
        write_to_file(sys.stdout, hacks, merge_dat)

def parse_args():
    def no_dot_in_extension(r_in):
        if '.' in r_in:
            raise argparse.ArgumentTypeError("extension must not have a dot")
        return r_in
    def searchpath_is_dir(p_in):
        if not os.path.isdir(p_in):
            raise argparse.ArgumentTypeError("{} must be a dir".format(p_in))
        return p_in
    types = argparse.RawTextHelpFormatter
    parser = argparse.ArgumentParser(description=desc_with_version, formatter_class=types)
    parser.add_argument('p', metavar=('search-path'), type=searchpath_is_dir, help=desc_search)
    parser.add_argument('r', metavar=('rom-type'), type=no_dot_in_extension, help=desc_ext)

    if platform.platform != "Windows": #options not compatible for lack of anonymous fifo and xattr
        parser.add_argument('-o', metavar=('output-file'), type=FileType('a+', encoding='utf-8'), help=desc_output)
        parser.add_argument('-d', metavar=('xml-file'), type=FileType('r', encoding='utf-8'), help=desc_xml)
        parser.add_argument('-i', action='store_true', help=desc_ignore)
        if xattr_available:
            parser.add_argument('-x', action='store_true', help=desc_forcexattr)
            parser.add_argument('-s', action='store_true', help=desc_bailout)
        else:
            parser.add_argument('-x', action='store_const', const=False, default=False, help=argparse.SUPPRESS)
            parser.add_argument('-s', action='store_const', const=False, default=False, help=argparse.SUPPRESS)
        parser.add_argument('-t', action='store_true', help=desc_check)
    return parser

def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL) # Make Ctrl+C work
    parser = parse_args()
    args = parser.parse_args()
    try:
        if platform.platform == "Windows": #force only version check
            make_dat(args.p, args.r, None, None, None, False, True, False)
            return 0

        #for early failure instead of failing when trying later
        flips = which('flips')
        xdelta = which('xdelta3')

        if args.i and not args.d:
            error("error: -i option requires -d option to whitelist roms on the dat")
            return 1
        if args.t and (args.o or args.d or args.i or args.x or args.s):
            error("error: -t option can't be used with other options")
            return 1
        if args.s and (args.o or args.d or args.i or args.t):
            error("error: -s option can't be used with options other than -x")
            return 1

        #'a+' opens for reading and writing, creating if necessary in append mode
        #seek to zero to read entries. If it all reads well, and processes well,
        #a new file will be moved over this file. Why not 'r'? To prevent user
        #giving '-' (stdout) and expecting it to work. Ommiting -o will write to stdout
        if args.o:
            args.o.seek(0)
            dat = hack_dat(args.o)
        else:
            dat = None

        make_dat(args.p, args.r, args.o, dat, args.d, args.i, args.t, args.x, args.s)
    except ParseException as e: #fail early for parsing this to prevent data loss
        error("error: {} parsing dat : {}".format(args.m.name, e))
        return 1
    except EXENotFoundError as e:
        error('error: rhdndat needs {} on its location, the current dir, or the OS path'.format(e.executable))
        p = os.path.dirname(sys.argv[0])
        if(os.access(p, os.W_OK|os.X_OK)):
            uri = Path(p).as_uri()
        else:
            uri = Path(os.getcwd()).as_uri()
        error(' suggested path: {}'.format(uri))
        return 1
    except VersionFileURLError as e:
        error('error: version file url connection failure')
        error(' file: {}'.format(Path(e.versionfile).as_uri()))
        error(' url:  {}'.format(e.url))
        return 1
    except VersionFileSyntaxError as e:
        error('error: version files repeat two lines, a version string and a romhacking url')
        error(' file: {}'.format(Path(e.versionfile).as_uri()))
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
