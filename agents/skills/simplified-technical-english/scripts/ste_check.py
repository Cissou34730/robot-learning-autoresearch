#!/usr/bin/env python3
"""ste_check.py - a check tool for ASD-STE100 Simplified Technical English.

This tool finds violations of the STE writing rules in text or Markdown.
It uses only the Python standard library.

Usage:
    python3 ste_check.py [--mode procedural|descriptive|mixed] FILE...
    python3 ste_check.py --glossary contracts/glossary.md FILE...
    cat draft.txt | python3 ste_check.py --mode procedural

The tool ignores code blocks, inline code, URLs, and YAML frontmatter.
Exit code 0 = no errors. Exit code 1 = one or more errors.
"""

import argparse
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- constants

# Rule 3.5: the only approved "-ing" words in the STE dictionary.
ING_APPROVED = {
    "mating",
    "missing",
    "remaining",  # adjectives
    "lighting",
    "opening",
    "routing",
    "servicing",  # nouns
    "during",  # preposition
}

# Words that end in "ing" where "ing" is not a verb suffix.
ING_NOT_SUFFIX = {
    "ring",
    "spring",
    "string",
    "king",
    "thing",
    "wing",
    "sing",
    "bring",
    "sting",
    "swing",
    "nothing",
    "anything",
    "everything",
    "something",
    "bearing",
    "ceiling",
    "morning",
    "evening",
}

# Rule 3.2 and the dictionary: approved helping verbs are CAN, MUST, WILL.
BANNED_MODALS = {"should", "would", "may", "might", "shall", "ought"}

CONTRACTION = re.compile(
    r"\b\w+n't\b|\b\w+'(?:re|ll|ve|m)\b|"
    r"\b(?:it|that|there|what|let|who|here|he|she)'s\b",
    re.IGNORECASE,
)

HAVE_PARTICIPLE = re.compile(
    r"\b(?:has|have|had)\s+(?:been|\w+ed|done|made|gone|put|set|cut|kept|held|"
    r"taken|given|found|left|lost|meant|sent|shown|told|built|become|begun|"
    r"broken|brought|come|fallen|felt|got|gotten|grown|known|read|run|seen|"
    r"spoken|thrown|worn|written)\b",
    re.IGNORECASE,
)

COMPLEX_PASSIVE = re.compile(
    r"\b(?:can|will|must|could|would|should|may|might|shall)\s+"
    r"(?:not\s+)?be\s+\w+(?:ed|en)\b|"
    r"\b(?:is|are|was|were)\s+to\s+be\s+\w+(?:ed|en)\b",
    re.IGNORECASE,
)

PASSIVE_BY = re.compile(
    r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+\s+)?\w+(?:ed|en)\s+by\b",
    re.IGNORECASE,
)

BE_ING = re.compile(r"\b(?:is|are|was|were|be|been|am)\s+\w+ing\b", re.IGNORECASE)

SENT_SPLIT = re.compile(r"(?<=[.!?:])\s+")
WORDISH = re.compile(r"[A-Za-z0-9'&/’-]+")

LIMITS = {"procedural": 20, "descriptive": 25, "mixed": 25}


# ---------------------------------------------------------------- helpers


def strip_markdown(text):
    """Remove parts of the text that the STE rules do not control."""
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.DOTALL)  # frontmatter
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)  # code blocks
    text = re.sub(r"`[^`\n]+`", " CODE ", text)  # inline code
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)  # links
    text = re.sub(r"https?://\S+", " URL ", text)  # bare URLs
    text = re.sub(r"^>.*$", " ", text, flags=re.MULTILINE)  # block quotes
    # quoted text counts as one word and is not controlled (rule 8.6)
    text = re.sub(r"\"[^\"\n]*\"|“[^”\n]*”", " QUOTED ", text)
    return text


def count_words(sentence):
    """Count words with the STE conventions of section 8.

    A number, an identifier, a hyphenated group, and text in
    parentheses each count as one word.
    """
    s = re.sub(r"\([^)]*\)", " PAREN ", sentence)  # rule 8.5
    s = re.sub(r"\*\*|\*|__|_|#+", " ", s)  # markdown marks
    tokens = WORDISH.findall(s)  # hyphenated group = 1 (rule 8.7)
    return len(tokens)


def iter_sentences(block):
    """Divide a text block into sentences."""
    for part in SENT_SPLIT.split(block):
        part = part.strip()
        if part and WORDISH.search(part):
            yield part


def load_word_list(path):
    """Read word-list.md and return the set of approved word forms."""
    approved = set()
    line_re = re.compile(
        r"^([A-Z][A-Z' -]*[A-Z])\s+\((\w+(?:, \w+)*)\)(?:\s+\[(.*)\])?"
    )
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = line_re.match(line)
        if not m:
            continue
        head, _pos, forms = m.groups()
        for w in head.split():
            approved.add(w.lower())
        if forms:
            for f in forms.split(","):
                for w in f.strip().split():
                    approved.add(w.lower())
        # plurals of nouns (rule: plural of a countable noun is approved)
        if "(n)" in line:
            word = head.lower()
            approved.add(word + "s")
            if word.endswith(("s", "x", "ch", "sh")):
                approved.add(word + "es")
            if word.endswith("y") and word[-2:-1] not in "aeiou":
                approved.add(word[:-1] + "ies")
    return approved


# ---------------------------------------------------------------- checks


class Glossary:
    """Project terms and the words that the project does not use for them.

    The glossary is a Markdown file. Each table that has a "Term" column and a
    "Do not use" column gives one term per row. The "Do not use" cell lists
    comma-separated words or phrases; an em dash or an empty cell lists none.
    """

    def __init__(self, path):
        self.terms = []
        self.banned = {}
        header = None
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.startswith("|"):
                header = None
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if header is None:
                lowered = [c.lower() for c in cells]
                if "term" in lowered and "do not use" in lowered:
                    header = (lowered.index("term"), lowered.index("do not use"))
                continue
            if set("".join(cells)) <= set("-: "):
                continue
            term = re.sub(r"[*`]", "", cells[header[0]]).strip()
            if term:
                self.terms.append(term.lower())
            avoid = re.sub(r"[*`]", "", cells[header[1]]).strip()
            for word in avoid.split(","):
                word = word.strip().lower()
                if word and word not in {"—", "-"}:
                    self.banned[word] = term
        self.terms.sort(key=len, reverse=True)

    def words(self):
        return {w for term in self.terms for w in re.findall(r"[a-z]+", term)}

    def check(self, par, report, loc):
        masked = " ".join(par.lower().split())
        # Paths, file names and identifiers are technical names, also without code format.
        masked = re.sub(
            r"\S*[/_]\S*|\b\w+\.(?:zip|json|jsonl|md|py|xml|txt)\b", " NAME ", masked
        )
        for term in self.terms:
            masked = re.sub(rf"\b{re.escape(term)}s?\b", " TERM ", masked)
        for word, term in self.banned.items():
            if re.search(rf"\b{re.escape(word)}\b", masked):
                report.error(loc, "glossary", f'"{word}": use the term "{term}".')


class Report:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.unknown = {}

    def error(self, loc, rule, msg):
        self.errors.append((loc, rule, msg))

    def warn(self, loc, rule, msg):
        self.warnings.append((loc, rule, msg))


def check_sentence(sent, mode, report, loc):
    limit = LIMITS[mode]
    n = count_words(sent)
    head = sent if len(sent) <= 60 else sent[:57] + "..."
    if n > 25:
        report.error(loc, "5.1/6.3", f'sentence has {n} words (max {limit}): "{head}"')
    elif n > 20:
        if mode == "procedural":
            report.error(loc, "5.1", f'sentence has {n} words (max 20): "{head}"')
        elif mode == "mixed":
            report.warn(
                loc, "5.1", f'sentence has {n} words (max 20 if procedural): "{head}"'
            )

    if ";" in sent:
        report.error(loc, "8.1", f'semicolon found: "{head}". Write two sentences.')

    m = CONTRACTION.search(sent)
    if m:
        report.error(loc, "4.2", f'contraction "{m.group(0)}": write the full words.')

    m = HAVE_PARTICIPLE.search(sent)
    if m:
        report.error(
            loc,
            "3.4",
            f'helping verb structure "{m.group(0)}": use the simple past tense.',
        )

    m = COMPLEX_PASSIVE.search(sent)
    if m:
        report.error(
            loc, "3.4", f'complex passive "{m.group(0)}": make the sentence active.'
        )

    m = PASSIVE_BY.search(sent)
    if m:
        report.error(
            loc, "3.6", f'passive voice "{m.group(0)}": make the agent the subject.'
        )

    m = BE_ING.search(sent)
    if m:
        tail = m.group(0).split()[-1].lower()
        if tail not in ING_APPROVED:
            report.error(
                loc, "3.5", f'progressive form "{m.group(0)}": use a simple tense.'
            )

    for word in re.findall(r"[A-Za-z-]+", sent):
        lw = word.lower()
        if lw in BANNED_MODALS:
            report.error(
                loc,
                "3.2",
                f'"{word}" is not approved. Use "must" (requirement), "can" '
                f'(possibility), "will" (future), or remove it.',
            )
        elif lw == "could":
            report.warn(
                loc, "3.2", '"could" is approved only as the past tense of "can".'
            )
        elif lw.endswith("ing") and len(lw) > 4 and not word.isupper():
            if lw not in ING_APPROVED and lw not in ING_NOT_SUFFIX:
                report.warn(
                    loc,
                    "3.5",
                    f'"{word}": an "-ing" form is permitted only in a technical name.',
                )


def check_vocab(text, report, approved):
    for word in re.findall(r"[A-Za-z]+(?:-[A-Za-z]+)*", text):
        if word.isupper() or any(c.isupper() for c in word[1:]):
            continue  # acronym, identifier, or quoted text
        lw = word.lower()
        if lw in approved or lw in ING_APPROVED or len(lw) <= 1:
            continue
        if all(p in approved for p in lw.split("-") if p):
            continue
        report.unknown[lw] = report.unknown.get(lw, 0) + 1


def check_paragraph(par, mode, report, loc, approved, glossary=None):
    sents = list(iter_sentences(par))
    if len(sents) > 6:
        report.error(loc, "6.6", f"paragraph has {len(sents)} sentences (max 6).")
    for s in sents:
        check_sentence(s, mode, report, loc)
    if approved:
        check_vocab(par, report, approved)
    if glossary:
        glossary.check(par, report, loc)


def check_text(text, mode, report, name, approved, glossary=None):
    text = strip_markdown(text)
    paragraphs = re.split(r"\n\s*\n", text)
    for i, par in enumerate(paragraphs):
        par = par.strip()
        if not par or not WORDISH.search(par):
            continue
        # a heading or a table row is a title or quoted text (rule 8.6)
        if par.startswith("#") or par.startswith("|"):
            continue
        lines = par.splitlines()
        bullet = re.compile(r"\s*(?:[-*+]|\d+\.)\s")
        # An indented line that follows a list item continues that item.
        joined = []
        for l in lines:
            if (
                joined
                and bullet.match(joined[-1])
                and l.startswith(" ")
                and not bullet.match(l)
            ):
                joined[-1] += " " + l.strip()
            else:
                joined.append(l)
        lines = joined
        items = [l for l in lines if bullet.match(l)]
        prose = [l for l in lines if not bullet.match(l)]
        # a list item counts as its own sentence (rule 8.4)
        for l in items:
            item = re.sub(r"^\s*(?:[-*+]|\d+\.)\s+", "", l)
            for s in iter_sentences(item):
                check_sentence(s, mode, report, f"{name}:list")
            if approved:
                check_vocab(item, report, approved)
            if glossary:
                glossary.check(item, report, f"{name}:list")
        if prose:
            check_paragraph(
                "\n".join(prose), mode, report, f"{name}:par{i + 1}", approved, glossary
            )


# ---------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser(
        description="Check text against the STE writing rules."
    )
    ap.add_argument("files", nargs="*", help="files to check (default: stdin)")
    ap.add_argument(
        "--mode",
        choices=["procedural", "descriptive", "mixed"],
        default="mixed",
        help="text type (default: mixed)",
    )
    ap.add_argument(
        "--word-list",
        default=None,
        help="path to word-list.md (default: ../references/word-list.md)",
    )
    ap.add_argument(
        "--no-vocab",
        action="store_true",
        help="do not check words against the approved word list",
    )
    ap.add_argument(
        "--glossary",
        default=None,
        help="project glossary: its terms are approved and their "
        "listed synonyms are errors",
    )
    args = ap.parse_args()

    glossary = Glossary(args.glossary) if args.glossary else None
    approved = None
    if not args.no_vocab:
        wl = args.word_list
        if wl is None:
            default = (
                Path(__file__).resolve().parent.parent / "references" / "word-list.md"
            )
            wl = default if default.exists() else None
        if wl:
            approved = load_word_list(wl)
            if glossary:
                approved |= glossary.words()

    report = Report()
    if args.files:
        for f in args.files:
            check_text(
                Path(f).read_text(encoding="utf-8"),
                args.mode,
                report,
                f,
                approved,
                glossary,
            )
    else:
        check_text(sys.stdin.read(), args.mode, report, "stdin", approved, glossary)

    for loc, rule, msg in report.errors:
        print(f"ERROR   {loc} [rule {rule}] {msg}")
    for loc, rule, msg in report.warnings:
        print(f"WARNING {loc} [rule {rule}] {msg}")
    if report.unknown:
        words = sorted(report.unknown, key=report.unknown.get, reverse=True)
        print(f"\nCHECK   {len(words)} words are not in the approved word list.")
        print("        Each must be an approved technical name or technical verb:")
        for chunk in [words[i : i + 10] for i in range(0, len(words), 10)]:
            print("        " + ", ".join(chunk))

    print(f"\nResult: {len(report.errors)} errors, {len(report.warnings)} warnings.")
    if not report.errors:
        print("The text obeys the STE structural rules that this tool can check.")
        print("This tool cannot make sure that each word has its approved meaning.")
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
