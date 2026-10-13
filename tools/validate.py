#!/usr/bin/env python3
"""Check the symbol table and the system docs against the rules in symbols/README.md and
systems/README.md. Prints one line per problem and exits 1 if there is any."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIBRARIES = {'crt', 'storm', 'lua'}

HEADERS = {
    'functions': ['address', 'size', 'name', 'name_from', 'system', 'class', 'signature',
                  'meaning', 'confidence', 'proof', 'finding', 'test'],
    'globals': ['address', 'type', 'name', 'name_from', 'system', 'meaning', 'confidence',
                'proof', 'finding'],
    'structs': ['name', 'size', 'vtable', 'system', 'meaning', 'confidence', 'proof', 'finding'],
    'fields': ['struct', 'offset', 'size', 'type', 'name', 'system', 'meaning', 'confidence',
               'proof', 'finding'],
}
SORT_KEYS = {
    'functions': lambda r: r['address'],
    'globals': lambda r: r['address'],
    'structs': lambda r: r['name'],
    'fields': lambda r: (r['struct'], r['offset']),
}

ADDRESS = re.compile(r'^0x[0-9a-f]{6}$')
OFFSET = re.compile(r'^0x[0-9a-f]{4}$')
DECIMAL = re.compile(r'^[1-9][0-9]*$')
SYSTEM = re.compile(r'^[a-z][a-z0-9]*$')
TEST = re.compile(r'^[a-z][a-z0-9_]*::[a-z][a-z0-9_]*$')
PASCAL = r'[A-Z][A-Za-z0-9]*'
METHOD_NAME = re.compile(rf'^(?:{PASCAL}::)+~?{PASCAL}$')
FREE_NAME = re.compile(rf'^{PASCAL}$')
LIBRARY_NAME = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*(?:::~?[A-Za-z_][A-Za-z0-9_]*)*(?:@[0-9]+)?$')
GLOBAL_NAME = re.compile(rf'^(?:s_[a-z][A-Za-z0-9]*|(?:{PASCAL}::)+vftable)$')
FIELD_NAME = re.compile(r'^(?:m_[a-z][A-Za-z0-9]*|__vfptr)$')
STRUCT_NAME = re.compile(rf'^{PASCAL}(?:::{PASCAL})*$')
VERB = re.compile(r'^[A-Z][A-Za-z]*s\b')
MEANING_BANNED = re.compile(r'\?|\bTODO\b|\b(?:probably|maybe|seems|likely)\b', re.I)
CLASSES = {'primitive', 'orchestration', 'host', 'boundary', 'unreached'}
PROOFS = {'verified': {'one', 'two', 'test'}, 'inferred': {'none'}}

LIMITS = {'meaning': 120, 'name': 48, 'signature': 160, 'overview': 200, 'title': 6,
          'claim': 120, 'table': 12, 'derivation': 200, 'code': 8, 'doc': 4000}
HEDGES = re.compile(r'\b(?:probably|likely|seems|appears to|roughly|maybe|should be|TODO|FIXME)\b', re.I)
SHOUTING = re.compile(r'NOTE:|\b(?:IMPORTANT|WARNING|CORRECTED|VERIFIED|INFERRED)\b')
HISTORY = re.compile(r'\b(?:previously|used to|no longer|originally|corrected|was wrong)\b', re.I)
FIRST_PERSON = re.compile(r'\b(?:[Ww]e|[Oo]ur|I)\b')
CITED = re.compile(r'`(0x[0-9a-f]{6})`')

BASE_SIZES = {'char': 1, 'int8_t': 1, 'uint8_t': 1, 'bool': 1, 'int16_t': 2, 'uint16_t': 2,
              'int': 4, 'unsigned int': 4, 'int32_t': 4, 'uint32_t': 4, 'float': 4,
              'double': 8, 'int64_t': 8, 'uint64_t': 8}

problems = []


def problem(where, message):
    problems.append(f'{where}: {message}')


def read_table(kind):
    path = ROOT / 'symbols' / f'{kind}.tsv'
    where = f'symbols/{kind}.tsv'
    if not path.exists():
        problem(where, 'missing')
        return []
    lines = path.read_text(encoding='utf-8').split('\n')
    if lines and lines[-1] == '':
        lines.pop()
    else:
        problem(where, 'does not end with a newline')
    header = HEADERS[kind]
    if not lines or lines[0].split('\t') != header:
        problem(f'{where}:1', 'header is not ' + ' '.join(header))
        return []
    rows = []
    for number, line in enumerate(lines[1:], start=2):
        cells = line.split('\t')
        if len(cells) != len(header):
            problem(f'{where}:{number}', f'{len(cells)} columns, not {len(header)}')
            continue
        row = dict(zip(header, cells))
        row['_where'] = f'{where}:{number}'
        rows.append(row)
    keys = [SORT_KEYS[kind](r) for r in rows]
    for previous, current, row in zip(keys, keys[1:], rows[1:]):
        if current <= previous:
            problem(row['_where'], 'out of order or duplicate key')
    return rows


def slug(heading):
    return re.sub(r'[^\w\- ]', '', heading.strip().lower()).replace(' ', '-')


def sections(text):
    parts = re.split(r'^## (.+)$', text, flags=re.M)
    return {slug(parts[i]): parts[i + 1] for i in range(1, len(parts), 2)}


def strip_code(text):
    text = re.sub(r'^```.*?^```', '', text, flags=re.M | re.S)
    return re.sub(r'`[^`]*`', '', text)


def words(text):
    return len(re.findall(r'\S+', text))


def type_size(ty, structs):
    ty = ty.strip()
    match = re.match(r'^.+\(\*\[([0-9]+)\]\)\(.*\)$', ty)
    if match:
        return 4 * int(match.group(1))
    match = re.match(r'^(.+?)\s*\[([0-9]+)\]$', ty)
    if match:
        unit = type_size(match.group(1), structs)
        return None if unit is None else unit * int(match.group(2))
    if ty.endswith('*'):
        return 4
    if ty.startswith('const '):
        return type_size(ty[6:], structs)
    if ty in BASE_SIZES:
        return BASE_SIZES[ty]
    if ty in structs:
        return int(structs[ty]['size'])
    return None


def check_common(row, anchors, mention):
    where = row['_where']
    meaning = row['meaning']
    if not meaning:
        problem(where, 'meaning is empty')
    else:
        if len(meaning) > LIMITS['meaning']:
            problem(where, f'meaning is {len(meaning)} characters, over {LIMITS["meaning"]}')
        if meaning.endswith('.'):
            problem(where, 'meaning ends with a period')
        if not VERB.match(meaning):
            problem(where, 'meaning does not start with a verb')
        if MEANING_BANNED.search(meaning):
            problem(where, 'meaning has a banned word: ' + MEANING_BANNED.search(meaning).group(0))
    if not SYSTEM.match(row['system']):
        problem(where, f'system {row["system"]!r} is not a lowercase word')
    confidence, proof, finding = row['confidence'], row['proof'], row['finding']
    if confidence not in PROOFS:
        problem(where, f'confidence {confidence!r} is not verified or inferred')
    elif proof not in PROOFS[confidence]:
        problem(where, f'{confidence} takes proof ' + ' or '.join(sorted(PROOFS[confidence])))
    if confidence == 'verified' and not finding:
        problem(where, 'verified needs a finding')
    if finding:
        if finding not in anchors:
            problem(where, f'finding {finding} does not resolve to an entry')
        elif mention and mention not in anchors[finding]:
            problem(where, f'finding {finding} does not mention {mention}')


def check_name(row, pattern, what):
    name = row['name']
    library = row.get('name_from') == 'idb' or row['system'] in LIBRARIES
    if not name:
        return
    if len(name) > LIMITS['name']:
        problem(row['_where'], f'name is {len(name)} characters, over {LIMITS["name"]}')
    if library:
        if not LIBRARY_NAME.match(name):
            problem(row['_where'], f'name {name!r} is not an identifier')
    elif not pattern(name):
        problem(row['_where'], f'name {name!r} breaks the naming rule for {what}')


def main():
    docs = {}
    for path in sorted((ROOT / 'systems').rglob('*.md')):
        if path == ROOT / 'systems' / 'README.md':
            continue
        key = path.relative_to(ROOT / 'systems').with_suffix('').as_posix()
        docs[key] = path
    written = {key.split('/')[0] for key in docs}
    anchors = {}
    for key, path in docs.items():
        for anchor, body in sections(path.read_text(encoding='utf-8')).items():
            anchors[f'{key}#{anchor}'] = body
    for anchor, body in sections((ROOT / 'METHOD.md').read_text(encoding='utf-8')).items():
        anchors[f'METHOD#{anchor}'] = body

    functions = read_table('functions')
    globals_ = read_table('globals')
    structs_rows = read_table('structs')
    fields = read_table('fields')
    structs = {}
    for row in structs_rows:
        if row['name'] in structs:
            problem(row['_where'], f'struct {row["name"]} appears twice')
        structs[row['name']] = row

    names = {}
    extents = []
    for kind, rows in (('function', functions), ('global', globals_)):
        spans = []
        for row in rows:
            where = row['_where']
            if not ADDRESS.match(row['address']):
                problem(where, f'address {row["address"]!r} is not 0x and six lowercase hex digits')
                continue
            if row['name_from'] not in ('', 'idb'):
                problem(where, 'name_from is idb or empty')
            if row['name']:
                if row['name'] in names:
                    problem(where, f'name {row["name"]} is also used at {names[row["name"]]}')
                names[row['name']] = row['address']
            check_common(row, anchors, row['address'])
            start = int(row['address'], 16)
            if kind == 'function':
                check_name(row, lambda n: METHOD_NAME.match(n) or FREE_NAME.match(n), 'functions')
                size = int(row['size']) if DECIMAL.match(row['size']) else None
                if size is None:
                    problem(where, f'size {row["size"]!r} is not a positive decimal')
                cls = row['class']
                if cls and cls not in CLASSES:
                    problem(where, f'class {cls!r} is not one of ' + ', '.join(sorted(CLASSES)))
                if not cls and row['system'] in written:
                    problem(where, f'class is required: {row["system"]} has a doc')
                if cls == 'unreached' and row['test']:
                    problem(where, 'an unreached function has no test')
                if row['test'] and not all(TEST.match(t) for t in row['test'].split(', ')):
                    problem(where, f'test {row["test"]!r} is not crate::test_fn')
                if len(row['signature']) > LIMITS['signature']:
                    problem(where, f'signature is over {LIMITS["signature"]} characters')
            else:
                check_name(row, GLOBAL_NAME.match, 'globals')
                size = type_size(row['type'], structs)
                if size is None:
                    problem(where, f'type {row["type"]!r} has no known size')
            if size:
                spans.append((start, start + size, row))
                extents.append((start, start + size))
        spans.sort(key=lambda s: s[0])
        for (s0, e0, r0), (s1, e1, r1) in zip(spans, spans[1:]):
            if s1 < e0:
                problem(r1['_where'], f'{r1["address"]} lies inside {r0["address"]}')
    seen = {}
    for row in functions + globals_:
        if row['address'] in seen:
            problem(row['_where'], f'address {row["address"]} also has a row at {seen[row["address"]]}')
        seen[row['address']] = row['_where']
    addresses = {row['address']: row for row in globals_}

    for row in structs_rows:
        where = row['_where']
        library = row['system'] in LIBRARIES
        if not (LIBRARY_NAME if library else STRUCT_NAME).match(row['name']):
            problem(where, f'struct name {row["name"]!r} breaks the naming rule')
        if not DECIMAL.match(row['size']):
            problem(where, f'size {row["size"]!r} is not a positive decimal')
        if row['vtable'] and row['vtable'] not in addresses:
            problem(where, f'vtable {row["vtable"]} is not a row of globals.tsv')
        check_common(row, anchors, None)

    occupied = {}
    for row in fields:
        where = row['_where']
        struct = structs.get(row['struct'])
        if struct is None:
            problem(where, f'struct {row["struct"]} is not a row of structs.tsv')
            continue
        library = struct['system'] in LIBRARIES
        if not (LIBRARY_NAME if library else FIELD_NAME).match(row['name']):
            problem(where, f'field name {row["name"]!r} breaks the naming rule')
        if not OFFSET.match(row['offset']) or not DECIMAL.match(row['size']):
            problem(where, 'offset is 0x and four hex digits, size a positive decimal')
            continue
        offset, size = int(row['offset'], 16), int(row['size'])
        if offset + size > int(struct['size']):
            problem(where, f'field ends past the {struct["size"]}-byte struct')
        expected = type_size(row['type'], structs)
        if expected is None:
            problem(where, f'type {row["type"]!r} has no known size')
        elif expected != size:
            problem(where, f'size {size} differs from the size of {row["type"]}, {expected}')
        names_here, spans_here = occupied.setdefault(row['struct'], (set(), []))
        if row['name'] in names_here:
            problem(where, f'field {row["name"]} appears twice in {row["struct"]}')
        names_here.add(row['name'])
        for start, end in spans_here:
            if offset < end and start < offset + size:
                problem(where, f'field overlaps another field of {row["struct"]}')
        spans_here.append((offset, offset + size))
        check_common(row, anchors, None)

    for key, path in docs.items():
        check_doc(key, path, functions)

    for path in sorted(ROOT.rglob('*.md')):
        if any(part.startswith('.') for part in path.relative_to(ROOT).parts):
            continue
        for number, line in enumerate(path.read_text(encoding='utf-8').split('\n'), start=1):
            for cited in CITED.findall(line):
                value = int(cited, 16)
                if not any(start <= value < end for start, end in extents):
                    problem(f'{path.relative_to(ROOT)}:{number}', f'{cited} resolves to no row')

    for line in problems:
        print(line)
    print(f'{len(functions)} functions, {len(globals_)} globals, {len(structs_rows)} structs, '
          f'{len(fields)} fields, {len(docs)} system docs: {len(problems)} problems')
    return 1 if problems else 0


def check_doc(key, path, functions):
    where = path.relative_to(ROOT).as_posix()
    text = path.read_text(encoding='utf-8')
    system = key.split('/')[0]
    if words(text) > LIMITS['doc']:
        problem(where, f'{words(text)} words, over {LIMITS["doc"]}; split by topic')
    lines = text.split('\n')
    if not lines[0].startswith('# '):
        problem(f'{where}:1', 'the doc starts with "# <system>"')
    in_code, code_start = False, 0
    for number, line in enumerate(lines, start=1):
        if line.startswith('```'):
            if in_code and number - code_start - 1 > LIMITS['code']:
                problem(f'{where}:{code_start}', f'code block over {LIMITS["code"]} lines')
            in_code, code_start = not in_code, number
    in_code = False
    for number, line in enumerate(lines, start=1):
        if line.startswith('```'):
            in_code = not in_code
        if in_code or line.startswith('```'):
            continue
        prose = strip_code(line)
        for pattern, what in ((HEDGES, 'hedge'), (SHOUTING, 'shouting'), (HISTORY, 'history'),
                              (FIRST_PERSON, 'first person')):
            found = pattern.search(prose)
            if found:
                problem(f'{where}:{number}', f'{what}: {found.group(0)!r}')

    head, _, rest = text.partition('\n## ')
    roots = re.search(r'^Roots: (.+?)(?:\n\n|\Z)', head, flags=re.M | re.S)
    if not roots:
        problem(where, 'no Roots line before the first entry')
        overview = head
    else:
        overview = head[:roots.start()]
        owned = {r['address'] for r in functions if r['system'] == system}
        for root in CITED.findall(roots.group(1)):
            if root not in owned:
                problem(where, f'root {root} is not a function row of {system}')
    overview = overview.split('\n', 1)[1] if '\n' in overview else ''
    if words(overview) > LIMITS['overview']:
        problem(where, f'overview is {words(overview)} words, over {LIMITS["overview"]}')

    for title, body in re.findall(r'^## ([^\n]+)\n(.*?)(?=^## |\Z)', text, flags=re.M | re.S):
        entry = f'{where}#{slug(title)}'
        if words(title) > LIMITS['title']:
            problem(entry, f'title is {words(title)} words, over {LIMITS["title"]}')
        shape = re.search(r'^Addresses: (.+)\nConfidence: (.*)\nProof: (.*)\nTest: (.*)$',
                          body, flags=re.M)
        if not shape:
            problem(entry, 'no Addresses, Confidence, Proof and Test lines in that order')
            continue
        cited, confidence, proof, test = shape.groups()
        if not re.fullmatch(r'`0x[0-9a-f]{6}`(?:, `0x[0-9a-f]{6}`)*', cited):
            problem(entry, 'Addresses is a comma-separated list of `0x……` addresses')
        if confidence not in PROOFS:
            problem(entry, f'Confidence {confidence!r} is not verified or inferred')
        elif proof not in PROOFS[confidence]:
            problem(entry, f'{confidence} takes Proof ' + ' or '.join(sorted(PROOFS[confidence])))
        if test != 'none' and not all(re.fullmatch(r'`[a-z][a-z0-9_]*::[a-z][a-z0-9_]*`', t)
                                      for t in test.split(', ')):
            problem(entry, 'Test is none or a list of `crate::test_fn`')
        claim, derivation = body[:shape.start()], body[shape.end():]
        prose = [line for line in claim.split('\n') if not line.startswith('|')]
        if words('\n'.join(prose)) > LIMITS['claim']:
            problem(entry, f'claim is {words(chr(10).join(prose))} words, over {LIMITS["claim"]}')
        table_rows = [line for line in claim.split('\n')
                      if line.startswith('|') and not re.fullmatch(r'\|[-|: ]+\|', line)]
        if len(table_rows) - 1 > LIMITS['table']:
            problem(entry, f'table has {len(table_rows) - 1} rows, over {LIMITS["table"]}')
        if words(derivation) > LIMITS['derivation']:
            problem(entry, f'derivation is {words(derivation)} words, over {LIMITS["derivation"]}')


if __name__ == '__main__':
    sys.exit(main())
