"""
frontmatter.py — read the YAML-style header of a record (.md). Stdlib only, so no yaml.

    fm_block(text)   the header text between the opening and closing `---`, or None
    fm_fields(text)  flat {key: value} of strings, quotes stripped — for tools that read a few fields
    fm_parse(text)   the same, plus `- item` lists and null/~ as None — what dashboard.py needs

For reading only. Tools that rewrite a header in place (schema.py, org_floor.py,
method_sightings.py) keep their own exact-span regexes, because they must put back every byte
they did not mean to change.
"""
import re

KEY = re.compile(r"^([A-Za-z_][\w]*):\s*(.*)$")
ITEM = re.compile(r"^\s*-\s+")


def fm_block(text):
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    return None if end == -1 else text[3:end]


def fm_fields(text):
    out = {}
    for line in (fm_block(text) or "").splitlines():
        m = KEY.match(line)
        if m:
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


def fm_parse(text):
    data, cur = {}, None
    for line in (fm_block(text) or "").splitlines():
        if ITEM.match(line) and cur:
            if not isinstance(data.get(cur), list):
                data[cur] = []
            data[cur].append(line.strip()[1:].strip().strip('"').strip("'"))
            continue
        m = KEY.match(line)
        if not m:
            continue
        cur = m.group(1)
        v = m.group(2).strip().strip('"').strip("'")
        data[cur] = ("" if v == "" else None) if v.lower() in ("null", "~", "") else v
    return data
