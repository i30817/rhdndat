__version__ = '1.6.6'

import textwrap

libraries_error ='''\
Please install required libraries. You can install the most recent version with:

\tpip3 install --user beautifulsoup4 lxml pyparsing colorama xattr'''

desc_with_version ='''\
rhdndat {} : www.romhacking.net dat creator and update checker

Finds triples (rom file, softpatch file, version file) on the same directory,
uses version to check for romhacking.net updates, and creates a clrmamepro entry
on stdout or file for the result of each softpatch.

A softpatch filename is: 'rom filename - rom extension + patch extension' or
'rom filename - rom extension + '.reset.xdelta'' (special case for recognizing
hardpatched roms and revert patches).

version file is simply named 'version' and has a version number line followed
by a romhacking.net url line, repeated. These correspond to each hack or
translation.

If there is no patch file, but a version file exists, the extension matches, and
-d is used and does not recognize the rom, the file will be assumed to be
hardpatched, which can be avoided by passing -i.

During normal operation, for all roms rhdndat stores extended attributes
user.rom.md5, user.rom.crc32 and user.rom.sha1 in the rom file, and these
checksums refer to the 'patched' file, even if the patch is a softpatch.

This makes rhdndat faster by only checksumming again after version file
modification or after using the -x option.

The intended workflow is:

rhdnet dir romtype -t
<update the patches and version files here>

then one of two options:

rhdnet dir romtype -s
                      if you want to update the extended attributes of changed
                      version files dirs only
rhdnet dir romtype -o hackdat -d nointroxml
                      if you want to create or update a retroarch hack dat
                      and take the original names from a nointro xml
                      (used for translations only)

Requires flips (if trying to work with ips, bps) and xdelta3 (if trying to work
with xdelta) on path or the same directory, unless on a Windows OS.

On windows, rhdndat only checks versions, has no optional arguments and
flips/xdelta are not required.'''
desc_with_version = textwrap.dedent(desc_with_version.format(__version__))

desc_search ='''\
directory tree to search for (rom, patches and version) files

'''
desc_search = textwrap.dedent(desc_search)

desc_ext = 'extension (without dot) of roms to find patches for'

desc_output ='''\
if omitted writes to stdout, if not empty merge entries,
to override a entry, a new entry must list the same
romhacking urls as the older entry

'''
desc_output = textwrap.dedent(desc_output)

desc_xml ='''\
normally the name is from the romhacking.net hack page,
but this option picks up the game names from from this
clrmamepro .xml and the rom checksum (including if a
revert patch is available)

this allows adding unknown roms without a patch, which
can't normally be added for safety, albeit with the
romhacking page name (the dat blacklists the false
unknowns, such as music tracks in cd games)

it's your responsability to use a dat that matches the
game/set you're scanning to avoid false unknowns

'''
desc_xml = textwrap.dedent(desc_xml)

desc_ignore ='''\
don\'t allow roms with unknown original name to be added even
if the patches have a romhacking.net hack page, requires -d

'''
desc_ignore = textwrap.dedent(desc_ignore)

desc_forcexattr ='''\
recalculate the extended attributes of all rom files even if
the version file is unchanged, useful for silent updates, the
easy way to redo the checksums of files without version files

'''
desc_forcexattr = textwrap.dedent(desc_forcexattr)

desc_bailout ='''\
do not progress beyond setting the extended attributes,
exclusive option, except for -x

'''
desc_bailout = textwrap.dedent(desc_bailout)

desc_check ='''\
only test version numbers against remote version,
works without a patch present, exclusive option
'''
desc_check = textwrap.dedent(desc_check)

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

def getRegionCode(language):
    if not language:
        return None
    for (code, longcode) in languages:
        if language in longcode:
            return code.capitalize()
    return None



