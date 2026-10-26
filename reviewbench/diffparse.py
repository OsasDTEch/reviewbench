"""Tiny unified-diff parser.

We only care about *added* lines (the lines a reviewer would comment on) and the
line number they land on in the new file, so the parser stays deliberately small.
"""

import re
from dataclasses import dataclass

_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


@dataclass
class AddedLine:
    file: str
    line: int
    text: str


def parse_diff(diff: str):
    """Return the list of AddedLine(file, new_file_line_no, text) in a diff."""
    added = []
    cur_file = None
    new_ln = 0
    in_hunk = False
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            path = raw[4:].strip().split("\t")[0]
            if path.startswith("b/"):
                path = path[2:]
            cur_file = path
            in_hunk = False
            continue
        if raw.startswith("--- "):
            continue
        m = _HUNK.match(raw)
        if m:
            new_ln = int(m.group(1))
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if raw.startswith("+"):
            added.append(AddedLine(cur_file or "?", new_ln, raw[1:]))
            new_ln += 1
        elif raw.startswith("-"):
            # removed line: present only in the old file, does not advance new_ln
            continue
        elif raw.startswith("\\"):
            # "\ No newline at end of file" marker: not a line of content
            continue
        else:
            # context line (leading space) or blank
            new_ln += 1
    return added
