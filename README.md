# FH2M Translation Tool

FH2M Translation Tool exports translatable text from fheroes2 map files to CSV
and imports an edited CSV back into new map copies. It is intended for
translators who want to work in Excel, LibreOffice Calc, Google Sheets, or a
translation workflow built around CSV files.

The tool is self-contained, uses only the Python standard library, and supports
every language currently represented by `SupportedLanguage` in fheroes2.

## Requirements

- Python 3.10 or newer
- FH2M maps in format version 11 or newer for CSV import

No Python packages need to be installed.

## Quick start

Run the following commands from this repository. On Windows, `python` may be
replaced with `py` if that is how Python is installed.

List supported language codes:

```powershell
python fh2m_tool.py languages
```

Export source text from one map and prepare a Czech translation column:

```powershell
python fh2m_tool.py export "C:\Games\fheroes2\maps\4_dimensions.fh2m" "4_dimensions_cs.csv" --language cs
```

If the map already contains an embedded Czech translation, the tool places it
in the `translation` column. Otherwise, that column is empty and ready for a
new translation. The `english` column always contains the map's source text;
`--language cs` selects the translation layer, not the source language.

Edit only the `translation` column, then import the CSV:

```powershell
python fh2m_tool.py import "C:\Games\fheroes2\maps\4_dimensions.fh2m" "4_dimensions_cs.csv" "C:\Games\fheroes2\maps-translated" --language cs
```

The translated copy is written to
`C:\Games\fheroes2\maps-translated\4_dimensions.fh2m`. The source map is not
overwritten.

## Working with a directory of maps

Both `export` and `import` accept either one `.fh2m` file or a directory. A
single CSV can therefore carry strings for an entire map collection:

```powershell
python fh2m_tool.py export "C:\Games\fheroes2\maps" "maps_cs.csv" --language cs
python fh2m_tool.py import "C:\Games\fheroes2\maps" "maps_cs.csv" "C:\Games\fheroes2\maps-translated" --language cs
```

During import, only maps represented in the CSV are written. This also means a
CSV exported from a directory can later be used to import one particular map;
rows belonging to other maps are ignored:

```powershell
python fh2m_tool.py import "C:\Games\fheroes2\maps\4_dimensions.fh2m" "maps_cs.csv" "C:\Games\fheroes2\maps-translated" --language cs
```

## CSV format

The file is UTF-8 with a byte-order mark for reliable opening in spreadsheet
applications. Every field is quoted. It contains exactly three columns:

| Column | Purpose |
| --- | --- |
| `id` | Stable map-and-field identifier used during import |
| `english` | Source text from the map; must not be edited |
| `translation` | Existing embedded translation, or an empty cell if the selected language is not present |

Example:

```csv
"id","english","translation"
"4_dimensions.fh2m::base:name","Four Dimensions","Čtyři dimenze"
"4_dimensions.fh2m::sign:object:12345","Keep out!","Nevstupovat!"
```

The exported fields include:

- map name, description, and creator notes;
- daily events and rumors;
- castle and hero names;
- Sphinx riddles and every accepted answer;
- signs;
- adventure-map events.

Identifiers contain the source map filename, so rows from multiple maps can
coexist safely in one CSV. Do not modify the `id` or `english` columns.

## Supported languages

Use the two-letter code with `--language`:

| Code | Language | Map encoding |
| --- | --- | --- |
| `be` | Belarusian | Windows-1251 |
| `bg` | Bulgarian | Windows-1251 |
| `cs` | Czech | Windows-1250 |
| `da` | Danish | Windows-1252 |
| `de` | German | Windows-1252 |
| `el` | Greek | Windows-1253 |
| `en` | English | Windows-1252 |
| `eo` | Esperanto | Windows-1252 |
| `es` | Spanish | Windows-1252 |
| `fr` | French | Windows-1252 |
| `hu` | Hungarian | Windows-1250 |
| `it` | Italian | Windows-1252 |
| `nb` | Norwegian Bokmål | Windows-1252 |
| `nl` | Dutch | Windows-1252 |
| `pl` | Polish | Windows-1250 |
| `pt` | Portuguese | Windows-1252 |
| `ro` | Romanian | ISO-8859-16 |
| `ru` | Russian | Windows-1251 |
| `sk` | Slovak | Windows-1250 |
| `sv` | Swedish | Windows-1252 |
| `tr` | Turkish | Windows-1254 |
| `uk` | Ukrainian | Windows-1251 |
| `vi` | Vietnamese | Windows-1258 |

The map's source language cannot also be selected as its translation language.
Vietnamese NFC input is converted to the representation required by
Windows-1258 automatically.

## Validation and safety

Import is deliberately strict. Before writing a map, the tool checks that:

- the CSV header and every row are valid;
- IDs are unique and belong to the selected source map or directory;
- no required IDs are missing;
- source text in the `english` column has not changed since export;
- translations can be represented by the target language's map encoding;
- the target language differs from the map's source language;
- all non-translation data remains byte-for-byte unchanged after writing;
- other embedded language layers remain unchanged;
- the generated map can be parsed and contains the imported translation.

By default, an empty translation for a non-empty source string is rejected.
Use the following option only when blank translations are intentional:

```powershell
python fh2m_tool.py import source.fh2m translation.csv output --language cs --allow-empty-translations
```

The output directory must differ from the source directory. Existing source
maps are never modified in place.

## Older maps

FH2M versions 9 and 10 cannot store the current embedded translation structure.
Open and save such maps in the current fheroes2 map editor before using the CSV
import command. The normal CSV workflow intentionally refuses unsafe binary
version conversion.

## Command reference

```text
fh2m_tool.py languages
fh2m_tool.py export SOURCE OUTPUT.csv --language LANGUAGE
fh2m_tool.py import SOURCE INPUT.csv OUTPUT_DIRECTORY --language LANGUAGE
                    [--allow-empty-translations]
```

Run `python fh2m_tool.py --help` or append `--help` to a subcommand for the
authoritative command-line help.
