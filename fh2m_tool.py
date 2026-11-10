#!/usr/bin/env python3
"""Export and import embedded translations in fheroes2 FH2M map files.

The module intentionally has no third-party runtime dependencies. Its writer
changes only the selected language layer and verifies the result by parsing the
generated map again before returning success.
"""

import argparse
import csv
import hashlib
import json
import struct
import unicodedata
import zlib
from pathlib import Path

LANG = {
    0: "en",
    1: "fr",
    2: "pl",
    3: "de",
    4: "ru",
    5: "it",
    6: "cs",
    7: "es",
    8: "be",
    9: "bg",
    10: "da",
    11: "nl",
    12: "eo",
    13: "el",
    14: "hu",
    15: "nb",
    16: "pt",
    17: "ro",
    18: "sk",
    19: "sv",
    20: "tr",
    21: "uk",
    22: "vi",
}
LANG_ID = {code: lang for lang, code in LANG.items()}

def codec(lang):
    if lang in (2, 6, 14, 18):
        return 'cp1250'
    if lang in (4, 8, 9, 21):
        return 'cp1251'
    if lang == 13:
        return 'cp1253'
    if lang == 20:
        return 'cp1254'
    if lang == 22:
        return 'cp1258'
    if lang == 17:
        return 'iso8859_16'
    return 'cp1252'

class BinaryReader:
    """Read the big-endian primitive types used by the FH2M format."""

    def __init__(self, b, encoding='cp1252'):
        self.b = b
        self.p = 0
        self.encoding = encoding

    def raw(self, n):
        x = self.b[self.p:self.p + n]
        assert len(x) == n
        self.p += n
        return x

    def u8(self):
        return self.raw(1)[0]

    def u16(self):
        return struct.unpack('>H', self.raw(2))[0]

    def u32(self):
        return struct.unpack('>I', self.raw(4))[0]

    def string(self):
        return self.raw(self.u32()).decode(self.encoding)

    def vec(self, fn):
        return [fn() for _ in range(self.u32())]

    def array(self, fn, n):
        assert self.u32() == n
        return [fn() for _ in range(n)]

    def map(self, k, v):
        return [(k(), v()) for _ in range(self.u32())]

def p32(x):
    return struct.pack('>I', x)

def encs(s, encoding='cp1252'):
    b = s.encode(encoding)
    return p32(len(b)) + b

def encmap(items, kf, vf):
    return p32(len(items)) + b''.join((kf(k) + vf(v) for k, v in items))

def funds(r):
    [r.u32() for _ in range(7)]

def strings(r):
    return r.vec(r.string)

def map_u32_str(r):
    return dict(r.map(r.u32, r.string))

def sphinx_tr(r):
    return {'riddle': r.string(), 'answers': strings(r)}

def tr_format(r):
    return {'daily_events': strings(r), 'rumors': strings(r), 'castle_names': map_u32_str(r), 'hero_names': map_u32_str(r), 'sphinx': dict(r.map(r.u32, lambda: sphinx_tr(r))), 'signs': map_u32_str(r), 'adventure_events': map_u32_str(r)}

def enc_strvec(v, c):
    return p32(len(v)) + b''.join((encs(x, c) for x in v))

def enc_u32_strmap(d, c):
    return encmap(sorted(((int(k), v) for k, v in d.items())), p32, lambda s: encs(s, c))

def enc_tr(t, c):
    return enc_strvec(t['daily_events'], c) + enc_strvec(t['rumors'], c) + enc_u32_strmap(t['castle_names'], c) + enc_u32_strmap(t['hero_names'], c) + encmap(sorted(((int(k), v) for k, v in t['sphinx'].items())), p32, lambda v: encs(v['riddle'], c) + enc_strvec(v['answers'], c)) + enc_u32_strmap(t['signs'], c) + enc_u32_strmap(t['adventure_events'], c)




def skip_map(r, v):
    for _ in range(r.u32()):
        r.u32()
        v()

def parse(path):
    b = path.read_bytes()
    assert b[:6] == b'h2map\x00'
    r = BinaryReader(b[6:])
    version = r.u16()
    assert 9 <= version <= 13
    r.u8()
    r.u8()
    r.u8()
    r.u8()
    r.u8()
    r.vec(r.u8)
    r.array(r.u8, 6)
    r.u8()
    r.u8()
    r.u8()
    r.vec(r.u32)
    r.u8()
    r.vec(r.u32)
    width = r.u32()
    main_lang = r.u8()
    r.encoding = codec(main_lang)
    name = r.string()
    desc = r.string()
    notes = r.string()
    base_tr_start = r.p
    base = {}
    if version >= 11:
        for _ in range(r.u32()):
            lang = r.u8()
            old = r.encoding
            r.encoding = codec(lang)
            base[lang] = {'name': r.string(), 'description': r.string(), 'creator_notes': r.string()}
            r.encoding = old
    comp_start = 6 + r.p
    comp = zlib.decompress(b[comp_start:])
    c = BinaryReader(comp, codec(main_lang))
    c.vec(c.u32)
    tiles_start = c.p
    tiles = []
    for _ in range(c.u32()):
        tiles.append({'terrain': c.u16(), 'flags': c.u8(), 'objects': c.vec(lambda: (c.u32(), c.u8(), c.u32()))})
    tiles_end = c.p
    daily = []
    for _ in range(c.u32()):
        daily.append(c.string())
        c.u8()
        c.u8()
        c.u32()
        c.u32()
        funds(c)
    rumors = strings(c)
    standard_start = c.p
    standard = {}
    if version < 10:
        for _ in range(c.u32()):
            key = c.u32()
            standard[key] = c.array(c.u32, 3)
    after_standard = c.p
    castles = {}
    for _ in range(c.u32()):
        key = c.u32()
        castles[key] = c.string()
        c.array(c.u32, 5)
        c.array(c.u32, 5)
        c.u8()
        c.vec(c.u32)
        c.vec(c.u32)
        c.map(c.u8, c.u32)
        c.vec(c.u32)
        c.array(c.u32, 6)
    heroes = {}
    for _ in range(c.u32()):
        key = c.u32()
        heroes[key] = c.string()
        c.u32()
        c.array(c.u32, 5)
        c.array(c.u32, 5)
        c.array(c.u32, 14)
        c.array(c.u32, 14)
        c.vec(c.u32)
        c.u8()
        c.u8()
        c.array(c.u8, 8)
        c.array(c.u8, 8)
        c.u16()
        c.u32()
        [c.u16() for _ in range(5)]
        c.u8()
    sphinx = {}
    for _ in range(c.u32()):
        key = c.u32()
        sphinx[key] = {'riddle': c.string(), 'answers': strings(c)}
        c.u32()
        c.u32()
        funds(c)
    signs = {}
    for _ in range(c.u32()):
        key = c.u32()
        signs[key] = c.string()
    events = {}
    for _ in range(c.u32()):
        key = c.u32()
        events[key] = c.string()
        c.u8()
        c.u8()
        c.u8()
        c.u32()
        c.u32()
        funds(c)
        [c.u16() for _ in range(4)]
        c.u32()
        c.u8()
        c.u8()
        c.u32()
        c.u32()
    skip_map(c, lambda: c.vec(c.u32))
    skip_map(c, c.u8)
    if version > 9:
        skip_map(c, lambda: (c.u32(), c.u32(), c.u8(), c.vec(c.u32)))
        skip_map(c, lambda: (c.u32(), c.u32(), c.vec(c.u32)))
        skip_map(c, c.u32)
    tr_start = c.p
    translations = {}
    if version >= 11:
        for _ in range(c.u32()):
            lang = c.u8()
            old = c.encoding
            c.encoding = codec(lang)
            translations[lang] = tr_format(c)
            c.encoding = old
    assert c.p == len(comp)
    main = {'daily_events': daily, 'rumors': rumors, 'castle_names': castles, 'hero_names': heroes, 'sphinx': sphinx, 'signs': signs, 'adventure_events': events}
    return {'bytes': b, 'version': version, 'width': width, 'main_language': main_lang, 'name': name, 'description': desc, 'creator_notes': notes, 'base': base, 'main': main, 'translations': translations, 'comp_start': comp_start, 'comp': comp, 'tr_start': tr_start, 'base_tr_abs': 6 + base_tr_start, 'tiles': tiles, 'tiles_start': tiles_start, 'tiles_end': tiles_end, 'standard': standard, 'standard_start': standard_start, 'after_standard': after_standard}



def inject_data(src, x, csbase, cst, out, target_lang=6):
    assert x['version'] >= 11, 'safe byte-preserving injection requires FH2M v11+; upgrade older maps with the fheroes2 editor first'
    base_items = [(k, v) for k, v in x['base'].items() if k != target_lang] + [(target_lang, csbase)]
    base_bytes = p32(len(base_items)) + b''.join((bytes([k]) + encs(v['name'], codec(k)) + encs(v['description'], codec(k)) + encs(v.get('creator_notes', ''), codec(k)) for k, v in sorted(base_items)))
    tr_items = [(k, v) for k, v in x['translations'].items() if k != target_lang] + [(target_lang, cst)]
    comp = x['comp'][:x['tr_start']] + p32(len(tr_items)) + b''.join((bytes([k]) + enc_tr(v, codec(k)) for k, v in sorted(tr_items)))
    new = x['bytes'][:x['base_tr_abs']] + base_bytes + zlib.compress(comp)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(new)
    y = parse(out)
    assert y['base'][target_lang] == csbase and enc_tr(y['translations'][target_lang], codec(target_lang)) == enc_tr(cst, codec(target_lang))
    for k, v in x['base'].items():
        if k != target_lang:
            assert y['base'][k] == v
    for k, v in x['translations'].items():
        if k != target_lang:
            assert enc_tr(y['translations'][k], codec(k)) == enc_tr(v, codec(k))
    assert x['comp'][:x['tr_start']] == y['comp'][:y['tr_start']]
    assert x['bytes'][:x['base_tr_abs']] == y['bytes'][:y['base_tr_abs']]
    return {'source_sha256': hashlib.sha256(x['bytes']).hexdigest(), 'output_sha256': hashlib.sha256(new).hexdigest(), 'roundtrip': True}

def input_maps(path):
    if path.is_file():
        assert path.suffix.lower() == '.fh2m', f'not an .fh2m file: {path}'
        return [path]
    assert path.is_dir(), f'map path does not exist: {path}'
    maps = sorted(path.glob('*.fh2m'))
    assert maps, f'no .fh2m maps found in: {path}'
    return maps

def blank_translation(main):
    return {'daily_events': ['' for _ in main['daily_events']], 'rumors': ['' for _ in main['rumors']], 'castle_names': {key: '' for key in main['castle_names']}, 'hero_names': {key: '' for key in main['hero_names']}, 'sphinx': {key: {'riddle': '', 'answers': ['' for _ in value['answers']]} for key, value in main['sphinx'].items()}, 'signs': {key: '' for key in main['signs']}, 'adventure_events': {key: '' for key in main['adventure_events']}}

def csv_rows(path, parsed, lang):
    translated_base = parsed['base'].get(lang, {'name': '', 'description': '', 'creator_notes': ''})
    translated = parsed['translations'].get(lang, blank_translation(parsed['main']))
    prefix = path.name + '::'
    rows = []

    def add(locator, english, translation):
        rows.append({'id': prefix + locator, 'english': english, 'translation': translation})

    def item(values, index):
        return values[index] if index < len(values) else ''
    add('base:name', parsed['name'], translated_base.get('name', ''))
    add('base:description', parsed['description'], translated_base.get('description', ''))
    add('base:creator_notes', parsed['creator_notes'], translated_base.get('creator_notes', ''))
    for index, value in enumerate(parsed['main']['daily_events']):
        add(f'daily_event:{index}', value, item(translated['daily_events'], index))
    for index, value in enumerate(parsed['main']['rumors']):
        add(f'rumor:{index}', value, item(translated['rumors'], index))
    for key, value in parsed['main']['castle_names'].items():
        add(f'castle_name:object:{key}', value, translated['castle_names'].get(key, ''))
    for key, value in parsed['main']['hero_names'].items():
        add(f'hero_name:object:{key}', value, translated['hero_names'].get(key, ''))
    for key, value in parsed['main']['sphinx'].items():
        current = translated['sphinx'].get(key, {'riddle': '', 'answers': ['' for _ in value['answers']]})
        add(f'sphinx_riddle:object:{key}', value['riddle'], current['riddle'])
        for index, answer in enumerate(value['answers']):
            translated_answer = item(current['answers'], index)
            add(f'sphinx_answer:object:{key}:answer:{index}', answer, translated_answer)
    for key, value in parsed['main']['signs'].items():
        add(f'sign:object:{key}', value, translated['signs'].get(key, ''))
    for key, value in parsed['main']['adventure_events'].items():
        add(f'adventure_event:object:{key}', value, translated['adventure_events'].get(key, ''))
    return rows

def export_csv(src, out, language):
    lang = LANG_ID[language]
    rows = []
    for path in input_maps(src):
        parsed = parse(path)
        assert lang != parsed['main_language'], f'{path.name}: {language} is already the map source language'
        rows.extend(csv_rows(path, parsed, lang))
    ids = [row['id'] for row in rows]
    assert len(ids) == len(set(ids)), 'duplicate generated string IDs'
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=['id', 'english', 'translation'], quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)
    with out.open('r', encoding='utf-8-sig', newline='') as handle:
        check = list(csv.DictReader(handle))
    assert check == rows, 'CSV write/read roundtrip failed'
    return {'maps': len(input_maps(src)), 'rows': len(rows), 'language': language, 'output': str(out), 'utf8_bom': True}

def normalized(text):
    return text.replace('\r\n', '\n').replace('\r', '\n')

def encoding_text(text, lang):
    if lang != 22:
        return text
    output = []
    structural = {'̂', '̆', '̛'}
    for char in text:
        try:
            char.encode('cp1258')
            output.append(char)
            continue
        except UnicodeEncodeError:
            pass
        decomposed = unicodedata.normalize('NFD', char)
        base = decomposed[0]
        marks = decomposed[1:]
        letter = unicodedata.normalize('NFC', base + ''.join((mark for mark in marks if mark in structural)))
        encoded = letter + ''.join((mark for mark in marks if mark not in structural))
        encoded.encode('cp1258')
        output.append(encoded)
    return ''.join(output)

def build_translation(parsed, row_map, map_name, lang, allow_empty):
    expected = csv_rows(Path(map_name), parsed, lang)
    expected_by_id = {row['id']: row for row in expected}
    actual_ids = set(row_map)
    expected_ids = set(expected_by_id)
    missing = sorted(expected_ids - actual_ids)
    extra = sorted(actual_ids - expected_ids)
    assert not missing, f'{map_name}: CSV is missing {len(missing)} IDs, first: {missing[:3]}'
    assert not extra, f'{map_name}: CSV has {len(extra)} unknown IDs, first: {extra[:3]}'
    for row_id, row in row_map.items():
        assert normalized(row['english']) == normalized(expected_by_id[row_id]['english']), f'{row_id}: English source text was changed'
        row['translation'] = encoding_text(normalized(row['translation']), lang)
        if not allow_empty and row['english'] and (not row['translation']):
            raise AssertionError(f'{row_id}: translation is empty (use --allow-empty-translations to permit it)')
        try:
            row['translation'].encode(codec(lang))
        except UnicodeEncodeError as error:
            raise AssertionError(f'{row_id}: translation cannot be encoded using {codec(lang)}: {error}') from error
    base = {'name': '', 'description': '', 'creator_notes': ''}
    translated = blank_translation(parsed['main'])
    prefix = map_name + '::'

    def value(locator):
        return row_map[prefix + locator]['translation']
    base['name'] = value('base:name')
    base['description'] = value('base:description')
    base['creator_notes'] = value('base:creator_notes')
    for index in range(len(translated['daily_events'])):
        translated['daily_events'][index] = value(f'daily_event:{index}')
    for index in range(len(translated['rumors'])):
        translated['rumors'][index] = value(f'rumor:{index}')
    for key in translated['castle_names']:
        translated['castle_names'][key] = value(f'castle_name:object:{key}')
    for key in translated['hero_names']:
        translated['hero_names'][key] = value(f'hero_name:object:{key}')
    for key, item in translated['sphinx'].items():
        item['riddle'] = value(f'sphinx_riddle:object:{key}')
        for index in range(len(item['answers'])):
            item['answers'][index] = value(f'sphinx_answer:object:{key}:answer:{index}')
    for key in translated['signs']:
        translated['signs'][key] = value(f'sign:object:{key}')
    for key in translated['adventure_events']:
        translated['adventure_events'][key] = value(f'adventure_event:object:{key}')
    return (base, translated)

def import_csv(src, csv_path, out_dir, language, allow_empty):
    lang = LANG_ID[language]
    sources = {path.name: path for path in input_maps(src)}
    with csv_path.open('r', encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        assert reader.fieldnames == ['id', 'english', 'translation'], f'expected CSV columns id,english,translation; got {reader.fieldnames}'
        rows = list(reader)
    assert rows, 'CSV contains no translation rows'
    grouped = {}
    for row in rows:
        assert set(row) == {'id', 'english', 'translation'} and all((value is not None for value in row.values())), 'malformed CSV row or unexpected extra column'
        assert "::" in row["id"], f"invalid ID: {row['id']}"
        map_name = row['id'].split('::', 1)[0]
        if map_name not in sources and src.is_file():
            # A collection CSV may be reused for one selected map.
            continue
        assert map_name in sources, (
            f'CSV references a map not found in the source path: {map_name}'
        )
        target = grouped.setdefault(map_name, {})
        assert row["id"] not in target, f"duplicate CSV ID: {row['id']}"
        target[row['id']] = row
    assert grouped, 'CSV contains no rows for the selected source map or directory'
    src_resolved = src.resolve()
    out_resolved = out_dir.resolve()
    if src.is_dir():
        assert src_resolved != out_resolved, 'output directory must differ from source directory'
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for map_name, row_map in sorted(grouped.items()):
        source = sources[map_name]
        parsed = parse(source)
        assert parsed["version"] >= 11, (
            f"{map_name}: format v{parsed['version']} cannot store translations; "
            "open and save it with the current fheroes2 map editor first"
        )
        assert lang != parsed['main_language'], f'{map_name}: {language} is already the map source language'
        base, translated = build_translation(parsed, row_map, map_name, lang, allow_empty)
        output = out_dir / map_name
        result = inject_data(source, parsed, base, translated, output, lang)
        result.update({'map': map_name, 'output': str(output)})
        results.append(result)
    imported_rows = sum(len(row_map) for row_map in grouped.values())
    return {
        'maps': len(results),
        'rows': imported_rows,
        'language': language,
        'output_dir': str(out_dir),
        'results': results,
    }


def main():
    ap = argparse.ArgumentParser(description='Export and import fheroes2 FH2M map translations using an editable CSV file.', epilog='Example: %(prog)s export maps translations.csv --language cs')
    sub = ap.add_subparsers(dest='cmd', required=True)
    e = sub.add_parser(
        'export',
        help='export source strings and an existing or empty translation column to CSV',
    )
    e.add_argument('src', type=Path, help='an .fh2m file or a directory containing maps')
    e.add_argument('out', type=Path, help='output CSV path')
    e.add_argument('--language', '-l', choices=sorted(LANG_ID), required=True, help='translation language code')
    c = sub.add_parser('import', help='import an edited CSV into new map copies')
    c.add_argument('src', type=Path, help='the source .fh2m file or maps directory used for export')
    c.add_argument('csv', type=Path, help='edited CSV path')
    c.add_argument('out', type=Path, help='output directory for translated map copies')
    c.add_argument('--language', '-l', choices=sorted(LANG_ID), required=True, help='translation language code')
    c.add_argument('--allow-empty-translations', action='store_true', help='allow blank translations for non-empty source strings')
    sub.add_parser('languages', help='list all language codes supported by the engine')
    a = ap.parse_args()
    try:
        if a.cmd == 'export':
            print(json.dumps(export_csv(a.src, a.out, a.language), ensure_ascii=False, indent=2))
        elif a.cmd == 'import':
            print(json.dumps(import_csv(a.src, a.csv, a.out, a.language, a.allow_empty_translations), ensure_ascii=False, indent=2))
        else:
            print(json.dumps([{'id': lang, 'code': code, 'encoding': codec(lang)} for lang, code in LANG.items()], indent=2))
    except (AssertionError, UnicodeError, ValueError) as error:
        ap.error(str(error))
if __name__ == '__main__':
    main()
