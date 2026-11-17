"""Diagnostics to stderr (copy of the opt-in logger)."""
import os
import sys


def enabled():
    return True


def log(msg):
    print(f"JFLOG pid={os.getpid()} {msg}", file=sys.stderr, flush=True)
