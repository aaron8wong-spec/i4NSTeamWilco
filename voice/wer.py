"""Word error rate (Lane M, task M11). Plain edit distance on words, no extra packages.

WER = (substitutions + deletions + insertions) / words in the reference.

Two versions are reported:
  strict      lowercase, punctuation removed. "150 meters" against "one hundred fifty meters" is wrong.
  number-norm same, but runs of number words become digits on both sides first, so "fifty" and "50"
              match. Decimals and coordinates are not handled ("point four one four zero" stays words),
              so clips with coordinates still count those as errors.
"""
import re

_ONES = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen "
    "fifteen sixteen seventeen eighteen nineteen".split())}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split())
         if w != "_"}
_NUMWORDS = set(_ONES) | set(_TENS) | {"hundred", "thousand"}


def _tokens(text):
    text = text.lower().replace("-", " ")
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)      # 1,000 -> 1000
    return re.findall(r"[a-z0-9]+(?:\.\d+)?", text)


def _digits_for_run(run):
    total = current = 0
    for w in run:
        if w in _ONES:
            current += _ONES[w]
        elif w in _TENS:
            current += _TENS[w]
        elif w == "hundred":
            current = max(current, 1) * 100
        else:  # thousand
            total += max(current, 1) * 1000
            current = 0
    return str(total + current)


def normalize_numbers(tokens):
    """Replace each run of number words with one digit string. 'forty five' -> '45'.

    A run is cut where a new ones-word follows a ones-word ('one two'), so spoken digit strings
    stay separate instead of adding up.
    """
    out, run = [], []

    def flush():
        if run:
            out.append(_digits_for_run(run))
            run.clear()

    for t in tokens:
        if t in _NUMWORDS:
            if run and t in _ONES and run[-1] in _ONES:
                flush()
            run.append(t)
        else:
            flush()
            out.append(t)
    flush()
    return out


def word_errors(ref, hyp):
    """(errors, reference word count) from word-level edit distance."""
    r, h = ref, hyp
    prev = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        cur = [i] + [0] * len(h)
        for j in range(1, len(h) + 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r[i - 1] != h[j - 1]))
        prev = cur
    return prev[len(h)], len(r)


def wer(reference, hypothesis, number_norm=False):
    """(errors, reference words). Divide to get the rate. Empty reference gives (len(hyp), 0)."""
    r, h = _tokens(reference), _tokens(hypothesis)
    if number_norm:
        r, h = normalize_numbers(r), normalize_numbers(h)
    return word_errors(r, h)
