"""Small, shared argument parsers used by simulation command-line programs."""

import argparse


def positive_int(value):
    """Parse a positive integer for argparse options."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number
