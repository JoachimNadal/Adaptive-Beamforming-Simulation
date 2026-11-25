"""Documentation must not rot: links resolve and code blocks run."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
IGNORED = {"venv", "site-packages", "build", "results"}


def is_ignored(path):
    parts = path.relative_to(ROOT).parts
    return bool(IGNORED & set(parts)) or any(part.startswith(".") for part in parts[:-1])


PAGES = [p for p in ROOT.rglob("*.md") if not is_ignored(p)]
RUNNABLE = [ROOT / "README.md", ROOT / "Beamforming_Theory_to_Embedded_Guide.md"]


def anchors(text):
    """GitHub anchors of the headings of a page."""
    found = set()
    for heading in re.findall(r"^#+ (.+)$", re.sub(r"```.*?```", "", text, flags=re.S), re.M):
        slug = re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")
        found.add(slug)
    return found


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.relative_to(ROOT).as_posix())
def test_links_resolve(page):
    text = page.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^)\s]+)\)", re.sub(r"```.*?```", "", text, flags=re.S)):
        if re.match(r"https?://|mailto:", target):
            continue
        path, _, anchor = target.partition("#")
        linked = page if not path else (page.parent / path).resolve()
        assert linked.exists(), f"{target} does not exist"
        if anchor and linked.suffix == ".md":
            assert anchor in anchors(linked.read_text(encoding="utf-8")), f"no anchor {target}"


@pytest.mark.filterwarnings("ignore:FigureCanvasAgg")
@pytest.mark.parametrize("page", RUNNABLE, ids=lambda p: p.name)
def test_code_blocks_run(page):
    blocks = re.findall(r"```python\n(.*?)```", page.read_text(encoding="utf-8"), re.S)
    programs = [b for b in blocks if re.search(r"^(import|from) ", b, re.M)]
    assert programs
    for block in programs:
        exec(compile(block, page.name, "exec"), {})


def test_no_empty_file_or_placeholder():
    """Audit: 50 of 93 files were empty. Only package markers may be."""
    for path in ROOT.rglob("*"):
        if not path.is_file() or is_ignored(path) or path.name == "__init__.py":
            continue
        if path.suffix in (".py", ".md", ".c", ".h", ".toml"):
            assert path.stat().st_size > 2, f"{path} is empty"
