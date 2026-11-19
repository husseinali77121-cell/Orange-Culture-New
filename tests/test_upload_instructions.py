"""NEW_REPO_SETUP.md tells the user how many files go in each browser upload.

GitHub's web upload takes at most 100 files at a time. The table's numbers were
updated by hand at every release; this test recomputes them from the release
manifest, so a release that adds files cannot ship a table that is wrong or a
batch that GitHub would refuse.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _release_files():
    files = [ln.split("  ", 1)[1].strip() for ln in
             (ROOT / "RELEASE_MANIFEST.sha256").read_text(encoding="utf-8").splitlines()
             if ln and not ln.startswith("#")]
    return files + ["RELEASE_MANIFEST.sha256"]


def test_upload_batches_match_the_release_and_fit_githubs_limit():
    text = (ROOT / "NEW_REPO_SETUP.md").read_text(encoding="utf-8")
    files = _release_files()
    total = int(re.search(r"والبرنامج (\d+) ملف", text).group(1))
    assert total == len(files), f"NEW_REPO_SETUP says {total} files, the release has {len(files)}"

    rows = re.findall(r"^\| \*\*[^|]+\*\* \| ([^|]+) \| (\d+) \|$", text, flags=re.M)
    assert rows, "upload table not found"
    claimed, counted = set(), []
    rest_row = None
    for i, (what, n) in enumerate(rows):
        if "كل الباقي" in what:
            rest_row = (i, int(n))
            continue
        tops = re.findall(r"`([^`]+)`", what)
        claimed.update(tops)
        c = sum(1 for f in files if f.split("/", 1)[0] in tops)
        assert c == int(n), f"batch {i + 1} ({', '.join(tops)}): table says {n}, actual {c}"
        counted.append(c)
    assert rest_row is not None
    rest = sum(1 for f in files if f.split("/", 1)[0] not in claimed)
    assert rest == rest_row[1], f"the last batch: table says {rest_row[1]}, actual {rest}"
    for c in counted + [rest]:
        assert c <= 100, "a batch over 100 files is refused by GitHub's web upload"
