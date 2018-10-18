__version__ = '1.3.0'

import textwrap

libraries_error ='''\
Please install required libraries. You can install the most recent version with:

\tpip3 install --user beautifulsoup4 lxml pyparsing colorama'''

desc_with_version ='''\
rhdndat {} : www.romhacking.net dat creator 

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
with xdelta) on path or the same directory.'''
desc_with_version = textwrap.dedent(desc_with_version.format(__version__))

desc_search ='''\
directory tree to search for (rom, patches and version) files

if there is no (rom, romfilename patch) pair but a patch of 
the form \'romfilename.reset.xdelta\' is found, rom is treated 
as a hardpatched rom, -d will search for the checksum of the
original rom and the output will be the checksums of \'rom\'

if (rom, version) pair exists, but no patch, rom is treated
as hardpatched and printed unless -i is given

'''
desc_search = textwrap.dedent(desc_search)

desc_ext = 'extension (without dot) of roms to find patches for'

desc_output = 'output file, if ommited writes to stdout'

desc_merge ='''\
merge non-overriden entries from this source file
to override a entry, a new entry must list the same
romhacking urls as the older entry

'''
desc_merge = textwrap.dedent(desc_merge)

desc_xml ='''\
forces to pick up the translations game names from the rom 
checksum in this file, if checksum not in xml, the program 
picks names from hack page 

'''
desc_xml = textwrap.dedent(desc_xml)

desc_ignore ='''\
don\'t allow unrecognized roms to be added even if the patches
have a romhacking.net page, prevents (rom,version) without
patch from being added as hardpatches

'''
desc_ignore = textwrap.dedent(desc_ignore)

desc_check ='''\
only test version numbers against remote version, 
ignore -o, -m, -d or -i, works without a patch present
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



