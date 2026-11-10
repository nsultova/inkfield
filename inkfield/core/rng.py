"""All randomness comes from here, so the same seed always draws the same picture.

A seed may arrive as a number or as text from a form. It is read as a number (anything
unreadable becomes 0) and wrapped into 0 … 2**32 − 1.

`stream` names an independent sequence for the same seed: the piece draws from one stream and
the hand-wobble effect from another, so changing one never shifts the numbers the other sees.
"""
import zlib

import numpy as np


def make_rng(seed, stream: str = "") -> np.random.Generator:
    try:
        seed = int(float(seed))
    except (TypeError, ValueError, OverflowError):
        seed = 0
    seed %= 2**32
    return np.random.default_rng(np.random.SeedSequence([seed, zlib.crc32(stream.encode())]))
