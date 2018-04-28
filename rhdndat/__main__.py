#!/usr/bin/python3

import argparse, sys, os, shutil, struct, signal, hashlib, itertools, urllib.request, subprocess, tempfile, zlib
from itertools import product


try:
    from bs4 import BeautifulSoup
except Exception as e:
    print("Please install beautifulsoup. You can install the most recent version with 'pip3 install --user beautifulsoup4'", file=sys.stderr)
    sys.exit(1)


languages = [
    ('aa', 'Afar'), ('ab', 'Abkhazian'), ('af', 'Afrikaans'), ('ak', 'Akan'),
    ('sq', 'Albanian'), ('am', 'Amharic'), ('ar', 'Arabic'), ('an', 'Aragonese'),
    ('hy', 'Armenian'), ('as', 'Assamese'), ('av', 'Avaric'), ('ae', 'Avestan'),
    ('ay', 'Aymara'), ('az', 'Azerbaijani'), ('ba', 'Bashkir'), ('bm', 'Bambara'),
    ('eu', 'Basque'), ('be', 'Belarusian'), ('bn', 'Bengali'), ('bh', 'Bihari languages'),
    ('bi', 'Bislama'), ('bo', 'Tibetan'), ('bs', 'Bosnian'), ('br', 'Breton'),
    ('bg', 'Bulgarian'), ('my', 'Burmese'), ('ca', 'Catalan; Valencian'), ('cs', 'Czech'),
    ('ch', 'Chamorro'), ('ce', 'Chechen'),
    ('cu', 'Church Slavic; Old Slavonic; Church Slavonic; Old Bulgarian; Old Church Slavonic'),
    ('cv', 'Chuvash'), ('kw', 'Cornish'), ('co', 'Corsican'), ('cr', 'Cree'), ('cy', 'Welsh'),
    ('cs', 'Czech'), ('da', 'Danish'), ('de', 'German'),
    ('dv', 'Divehi; Dhivehi; Maldivian'), ('nl', 'Dutch; Flemish'), ('dz', 'Dzongkha'),
    ('el', 'Greek, Modern (1453-)'), ('en', 'English'), ('eo', 'Esperanto'),
    ('et', 'Estonian'), ('eu', 'Basque'), ('ee', 'Ewe'), ('fo', 'Faroese'),
    ('fa', 'Persian'), ('fj', 'Fijian'), ('fi', 'Finnish'), ('fr', 'French'),
    ('fy', 'Western Frisian'), ('ff', 'Fulah'), ('Ga', 'Georgian'), ('de', 'German'),
    ('gd', 'Gaelic; Scottish Gaelic'), ('ga', 'Irish'), ('gl', 'Galician'), ('gv', 'Manx'),
    ('el', 'Greek, Modern (1453-)'), ('gn', 'Guarani'), ('gu', 'Gujarati'),
    ('ht', 'Haitian; Haitian Creole'), ('ha', 'Hausa'), ('he', 'Hebrew'), ('hz', 'Herero'),
    ('hi', 'Hindi'), ('ho', 'Hiri Motu'), ('hr', 'Croatian'), ('hu', 'Hungarian'),
    ('hy', 'Armenian'), ('ig', 'Igbo'), ('is', 'Icelandic'), ('io', 'Ido'),
    ('ii', 'Sichuan Yi; Nuosu'), ('iu', 'Inuktitut'), ('ie', 'Interlingue; Occidental'),
    ('ia', 'Interlingua (International Auxiliary Language Association)'),
    ('id', 'Indonesian'), ('ik', 'Inupiaq'), ('is', 'Icelandic'), ('it', 'Italian'),
    ('jv', 'Javanese'), ('ja', 'Japanese'), ('kl', 'Kalaallisut; Greenlandic'),
    ('kn', 'Kannada'), ('ks', 'Kashmiri'), ('ka', 'Georgian'), ('kr', 'Kanuri'),
    ('kk', 'Kazakh'), ('km', 'Central Khmer'), ('ki', 'Kikuyu; Gikuyu'), ('rw', 'Kinyarwanda'),
    ('ky', 'Kirghiz; Kyrgyz'), ('kv', 'Komi'), ('kg', 'Kongo'), ('ko', 'Korean'),
    ('kj', 'Kuanyama; Kwanyama'), ('ku', 'Kurdish'), ('lo', 'Lao'), ('la', 'Latin'),
    ('lv', 'Latvian'), ('li', 'Limburgan; Limburger; Limburgish'), ('ln', 'Lingala'),
    ('lt', 'Lithuanian'), ('lb', 'Luxembourgish; Letzeburgesch'), ('lu', 'Luba-Katanga'),
    ('lg', 'Ganda'), ('mk', 'Macedonian'), ('mh', 'Marshallese'), ('ml', 'Malayalam'),
    ('mi', 'Maori'), ('mr', 'Marathi'), ('ms', 'Malay'), ('Mi', 'Micmac'), ('mk', 'Macedonian'),
    ('mg', 'Malagasy'), ('mt', 'Maltese'), ('mn', 'Mongolian'), ('mi', 'Maori'),
    ('ms', 'Malay'), ('my', 'Burmese'), ('na', 'Nauru'), ('nv', 'Navajo; Navaho'),
    ('nr', 'Ndebele, South; South Ndebele'), ('nd', 'Ndebele, North; North Ndebele'),
    ('ng', 'Ndonga'), ('ne', 'Nepali'), ('nl', 'Dutch; Flemish'),
    ('nn', 'Norwegian Nynorsk; Nynorsk, Norwegian'), ('nb', 'Bokmål, Norwegian; Norwegian Bokmål'),
    ('no', 'Norwegian'), ('oc', 'Occitan (post 1500)'), ('oj', 'Ojibwa'), ('or', 'Oriya'),
    ('om', 'Oromo'), ('os', 'Ossetian; Ossetic'), ('pa', 'Panjabi; Punjabi'), ('fa', 'Persian'),
    ('pi', 'Pali'), ('pl', 'Polish'), ('pt', 'Portuguese'), ('ps', 'Pushto; Pashto'),
    ('qu', 'Quechua'), ('rm', 'Romansh'), ('ro', 'Romanian; Moldavian; Moldovan'),
    ('ro', 'Romanian; Moldavian; Moldovan'), ('rn', 'Rundi'), ('ru', 'Russian'),
    ('sg', 'Sango'), ('sa', 'Sanskrit'), ('si', 'Sinhala; Sinhalese'), ('sk', 'Slovak'),
    ('sk', 'Slovak'), ('sl', 'Slovenian'), ('se', 'Northern Sami'), ('sm', 'Samoan'),
    ('sn', 'Shona'), ('sd', 'Sindhi'), ('so', 'Somali'), ('st', 'Sotho, Southern'),
    ('es', 'Spanish; Castilian'), ('sq', 'Albanian'), ('sc', 'Sardinian'), ('sr', 'Serbian'),
    ('ss', 'Swati'), ('su', 'Sundanese'), ('sw', 'Swahili'), ('sv', 'Swedish'),
    ('ty', 'Tahitian'), ('ta', 'Tamil'), ('tt', 'Tatar'), ('te', 'Telugu'), ('tg', 'Tajik'),
    ('tl', 'Tagalog'), ('th', 'Thai'), ('bo', 'Tibetan'), ('ti', 'Tigrinya'),
    ('to', 'Tonga (Tonga Islands)'), ('tn', 'Tswana'), ('ts', 'Tsonga'), ('tk', 'Turkmen'),
    ('tr', 'Turkish'), ('tw', 'Twi'), ('ug', 'Uighur; Uyghur'), ('uk', 'Ukrainian'),
    ('ur', 'Urdu'), ('uz', 'Uzbek'), ('ve', 'Venda'), ('vi', 'Vietnamese'),
    ('vo', 'Volapük'), ('cy', 'Welsh'), ('wa', 'Walloon'), ('wo', 'Wolof'),
    ('xh', 'Xhosa'), ('yi', 'Yiddish'), ('yo', 'Yoruba'), ('za', 'Zhuang; Chuang'),
    ('zh', 'Chinese'), ('zu', 'Zulu')
]

def Cc(s):
    s = s.lower()
    for p in product(*[(0,1)]*len(s)):
      yield ''.join( c.upper() if t else c for t,c in zip(p,s))

def getRegionCode(language):
    if not language:
        return None
    for (code, longcode) in languages:
        if language in longcode:
            return code.capitalize()
    return None

class ScriptError(Exception):
    def __init__(self, message, errors=None):
        super().__init__(message)
        self.errors = errors

class Hack:

    def __init__(self, metadata_tuples, language, rom_title):
        self.metadata_tuples = metadata_tuples
        self.language   = language and language.string #hacks have no language
        self.regioncode = language and getRegionCode(language)
        self.rom_title = rom_title

    def to_string(self, rom, size, crc, md5, sha1):
        #main name priority:
        # first hack with zero translations > rom_title > last translation > first hack
        # secondary name be:
        # [(last)T-lang by author] for 1+ T and 0 hacks (translations are only multiple if addendums)
        # [(last)T-lang by author + # Hacks] for 1+ T and 1+ hacks + 
        # [(first) Hack by author] for 0 T and 1 hack
        # [(first) Hack by author + # hacks] for 0 T and 1+ hack
        # (# is always equal to (number of translations + number of hacks -1) when it appears

        last_translation = None
        last_translation_author = None
        first_hack = None
        first_hack_author = None
        count_translations = 0
        count_hacks = 0

        for title, author, version, url in self.metadata_tuples:
            if "www.romhacking.net/translations" in url:
                count_translations = count_translations + 1
                last_translation = title
                last_translation_author = author
            elif  "www.romhacking.net/hacks" in url:
                count_hacks = count_hacks + 1
                if not first_hack:
                    first_hack = title
                    first_hack_author = author
            else:
                assert False

        main_title = self.rom_title
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
            title_suffix = "[T-{} by {}]".format(self.regioncode, last_translation_author)
        elif count_translations > 0 and count_hacks > 0:
            title_suffix = "[T-{} by {} + {} hacks]".format(self.regioncode, last_translation_author, cardinal_of_hacks)
        elif count_translations == 0 and count_hacks == 1:
            title_suffix = "[Hack by {}]".format(first_hack_author)
        elif count_translations == 0 and count_hacks > 0:
            title_suffix = "[Hack by {} + {} hacks]".format(first_hack_author, cardinal_of_hacks)
        else:
            assert False

        (title, author, version, url) = self.metadata_tuples[0]
        comments = "    comment \"{}\"".format(url)
        if "www.romhacking.net/translations" in url:
            description = "{} translation by {} version ({})".format(self.language, author, version)
        else:
            description = "{} hack by {} version ({})".format(title, author, version)
        for title, author, version, url in self.metadata_tuples[1:]:
            comments += "\n    comment \"{}\"".format(url)
            if "www.romhacking.net/translations" in url:
                description += " + {} translation by {} version ({})".format(self.language, author, version)
            else:
                description += " + {} hack by {} version ({})".format(title, author, version)

        remote_hack = '''
game (
    name "{} {}"
    description "{}"
    rom ( name "{}" size {} crc {} md5 {} sha1 {} )
{}
)'''.format(main_title, title_suffix, description, rom, size, crc, md5, sha1, comments)
        return remote_hack

from contextlib import contextmanager
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

    yield "{:08x}".format( hash_crc32 & 0xffffffff )

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

    crc = "{:08x}".format( hash_crc32 & 0xffffffff )
    md5 = hash_md5.hexdigest()
    sha1 = hash_sha1.hexdigest()

    yield (size, crc, md5, sha1)

def file_producer(source_filename, generator_function):
    BLOCKSIZE = 2 ** 20

    next(generator_function)
    with open(source_filename, "rb") as f:
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


def flips_producer(flips, patch, source, generator_function):
    BLOCKSIZE = 2 ** 20
    process = None
    next(generator_function)
    with named_pipes() as pipes:
        pipe = pipes[0]
        with subprocess.Popen([flips, "--exact", "-a", patch, source, pipe ], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL) as process:
            with open(pipe, 'rb') as fifo:
                bytes = fifo.read(BLOCKSIZE)
                while len(bytes) > 0:
                    generator_function.send(bytes)
                    bytes = fifo.read(BLOCKSIZE)
    
    #if a error occurred avoid writing bogus checksums
    if process.returncode != 0:
        raise ScriptError("error during patching, try to remove the header if a snes rom")

    return generator_function.send([])

def xdelta_producer(xdelta, patch, source, generator_function):
    BLOCKSIZE = 2 ** 20
    process = None
    next(generator_function)
    with named_pipes() as pipes:
        pipe = pipes[0]
        with subprocess.Popen([xdelta, "-d", "-s", source, patch, pipe ], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL) as process:
            with open(pipe, 'rb') as fifo:
                bytes = fifo.read(BLOCKSIZE)
                while len(bytes) > 0:
                    generator_function.send(bytes)
                    bytes = fifo.read(BLOCKSIZE)
    
    #if a error occurred avoid writing bogus checksums
    if process.returncode != 0:
        raise ScriptError("error during patching, try to remove the header if a snes rom")

    return generator_function.send([])

def patch_producer(patch, source, generator_function):
    if patch.endswith(".xdelta"):
        xdelta = which("xdelta3")
        if not xdelta:
            raise ScriptError("xdelta3 not found")
        return xdelta_producer(xdelta, patch, source, generator_function)
    else:
        flips = which("flips")
        if not flips:
            raise ScriptError("flips not found")
        return flips_producer(flips, patch, source, generator_function)

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
        raise ScriptError("has version file, but no valid contents")
    if not hacks_list:
        raise ScriptError("has version file, but no valid contents")
    for version, url in hacks_list:
        if not ("www.romhacking.net/translations" in url or "www.romhacking.net/hacks" in url):
            raise ScriptError("has non romhacking urls in version file")
    return hacks_list

def get_romhacking_data(rom, possible_metadata):
    metadata = []
    language = None
    for (version, url) in read_version_file(possible_metadata):
        page = urllib.request.urlopen(url).read()
        soup = BeautifulSoup(page, "lxml")
        info = soup.find("table", class_="entryinfo entryinfosmall").find("tbody")

        #hacks have no language
        tmp  = info.find("th", string="Language")
        tmp  = tmp and tmp.nextSibling.string
        #it's a error for a translation to have 1+ languages, whatever combination of patches there is
        if not language:
            language = tmp
        assert ( tmp == None or tmp == language ), 'language of a translation should never change with a addendum'

        authors = info.find("th", string="Released By").nextSibling
        authors_str = authors.string
        if not authors_str:
            authors = authors.findAll("a")
            authors_str = authors[0].string
            for author in authors[1:-1]:
                authors_str += ", {}".format(author.string)
            authors_str += " and {}".format(authors[-1].string)

        metadata += [(
            info.find("div").find("div").string, #main title
            authors_str,
            version, #the version we actually have
            url
        )]

        remote_version = info.find("th", string="Patch Version").nextSibling.string.strip()
        if remote_version and remote_version != version:
          print("warn: '{}' local '{}' != upstream '{}' versions".format(rom, version, remote_version), file=sys.stderr)
    return (metadata, language)

def get_dat_rom_name(dat, dat_crc32):
    dat_rom = dat.find("rom", crc=dat_crc32)
    if dat_rom:
        return dat_rom.parent['name']
    return None

def make_dat(searchdir, romtype, output_file, dat_file, unknown_remove, test_versions_only):
    skip_bytes = 0
    dat = None
    if dat_file:
        dat = BeautifulSoup(dat_file, "lxml")
        #needs to skip ines header. Might be needed for other dumping groups and systems?
        if dat.find("clrmamepro", header="No-Intro_NES.xml"):
            skip_bytes = 16

    flips = which("flips")
    xdelta = which("xdelta3")
    patchtypes = []
    if flips:
        patchtypes += [".bps", ".BPS", ".ips", ".IPS"]
    if xdelta:
        patchtypes += [".xdelta", ".XDELTA", ".reset.xdelta"]
    assert patchtypes, 'the program needs xdelta3, flips or both on the path or script dir'

    #this is probably over-zealous and slow but whatever
    romtypes   = list(Cc("."+romtype))


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
                        raise ScriptError("no patches and a version file, hardpatch possible, but -i given")
                    print("warn: '{}' : no patches and a version file, assume a hardpatch without reset".format(rom), file=sys.stderr)
                    softpatch = False

                if len(patches) > 1:
                    raise ScriptError("multiple possible patches found")

                if softpatch:
                    patch = patches[0]

                #if using dat file for name, find the rom on dat
                rom_title = None
                if dat and softpatch:
                    if skip_bytes == 0 and (patch.endswith(".bps") or patch.endswith(".BPS")):
                        #bps roms have 12 bytes footers with the source, destination and patch crc32s
                        #unfortunately, this doesn't work if the dat we're working with skips headers
                        #(except for SNES headers, which is the one header bps ignores when creating/applying a patch)
                        dat_crc32 = None
                        target = None
                        with open(patch, 'rb') as p:
                            p.seek(-12, os.SEEK_END)
                            dat_crc32 = "{:08x}".format( struct.unpack('I', p.read(4))[0]   )
                        
                        rom_title = get_dat_rom_name(dat, dat_crc32.upper())
                        if not rom_title:
                             rom_title = get_dat_rom_name(dat, dat_crc32.lower())
                    else:
                        crc32_generator = get_crc32(skip_bytes)
                        if patch.endswith(".reset.xdelta"): #it's a hardpatch
                            dat_crc32 = patch_producer(patch, absolute_rom, crc32_generator)
                        else:
                            dat_crc32 =  file_producer(absolute_rom, crc32_generator)
                        rom_title = get_dat_rom_name(dat, dat_crc32.upper())
                        if not rom_title:
                             rom_title = get_dat_rom_name(dat, dat_crc32.lower())

                    if unknown_remove and not rom_title:
                        raise ScriptError("checksum not found in dat")
                    elif not rom_title:
                        print("warn: '{}' : checksum not found on dat, but not skipped".format(rom), file=sys.stderr)

                hack = Hack(
                    metadata,
                    language,
                    rom_title
                )
                
                #this assumes that multiple hacks were already glued into a single softpatch if there are multiple urls
                checksums_generator = get_checksums()
                #hardpatch
                if not softpatch or patch.endswith(".reset.xdelta"):
                    (size, crc, md5, sha1) = file_producer(absolute_rom, checksums_generator)
                else:
                    (size, crc, md5, sha1) = patch_producer(patch, absolute_rom, checksums_generator)

                hackstr = hack.to_string(rom, size, crc, md5, sha1)

                if output_file:
                    output_file.write( hackstr )
                else:
                    print(hackstr, file=sys.stdout)

            except ScriptError as e: #let the default stop execution and print on other errors
                print("skip: '{}' : '{}'".format(rom, e), file=sys.stderr)
                continue

import textwrap
def main():
    parser = argparse.ArgumentParser(
description =textwrap.dedent("""
rhdndat: www.romhacking.net dat creator 

Finds triples (rom file, softpatch file, version file) on the same 
directory and creates a clrmamepro entry on stdout or file for the result of 
each softpatch. It can also serve as a notifier that a update is required by 
comparing local versions to remote romhacking.net versions.

A softpatch filename is: 'rom filename - rom extension + patch extension' or
'rom filename - rom extension + '.reset.xdelta'' (special case for recognizing
hardpatched roms and revert patches).

If there is no patch file, but a version file exists, and the extension matches,
the file will be assumed to be hardpatched, which can be avoided by passing -i.

version file is simply named 'version' and has a version number line followed 
by a romhacking.net url line, repeated. These correspond to each hack or 
translation on the softpatch.

Requires flips (if trying to work with ips, bps) and xdelta3 (if trying to work
with xdelta) on path or the same directory.""")
, formatter_class=argparse.RawTextHelpFormatter
)
    parser.add_argument('p', metavar=('search-path'), type=str, 
        help=textwrap.dedent("""\
directory tree to search for (rom, patches and version) files

if there is no (rom, romfilename patch) pair but a patch of 
the form \'romfilename.reset.xdelta\' is found, rom is treated 
as a hardpatched rom, -d will search for the checksum of the
original rom and the output will be the checksums of \'rom\'

if (rom, version) pair exists, but no patch, rom is treated
as hardpatched and printed unless -i is given

            """))
    parser.add_argument('r', metavar=('rom-type'), type=str, 
help='extension (without dot) of roms to find patches for')
    parser.add_argument('-o', metavar=('output-file'), default=None, 
type=argparse.FileType('w'), help='ouput file, if ommited writes to stdout')
    parser.add_argument('-d', metavar=('xml-file'), type=argparse.FileType('r'), 
help=textwrap.dedent("""\
forces to pick up the translations game names from the rom 
checksum in this file, if checksum not in xml, the program 
picks names from hack page 

    """))
    parser.add_argument('-i', action='store_true', 
help=textwrap.dedent("""\
don\'t allow unrecognized roms to be added even if the patches
have a romhacking.net page, prevents (rom,version) without
patch from being added as hardpatches

    """))
    parser.add_argument('-t', action='store_true', 
help=textwrap.dedent("""\
only test version numbers against remote version, 
ignore -o, -d or -i, works without a patch present
    """))
    args = parser.parse_args()
    

    signal.signal(signal.SIGINT, signal.SIG_DFL) # Make Ctrl+C work  

    if "." in args.r or not os.path.isdir(args.p):
        parser.print_help()
        return 1
    else:
        if args.t:
            args.o = None
            args.d = None
            args.i = False
        make_dat(args.p, args.r, args.o, args.d, args.i, args.t)
    return 0


if __name__ == "__main__":
    sys.exit(main())



