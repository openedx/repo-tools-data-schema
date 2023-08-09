"""
Functions for validating the schema of repo-tools-data.
"""

import collections
import csv
import difflib
import re

import yaml
from schema import Optional, Or, Schema
from yaml.constructor import ConstructorError


def valid_email(s):
    """Is this a valid email?"""
    return bool(
        isinstance(s, str) and
        re.search(r"^[^@ ]+@[^@ ]+\.[^@ ]+$", s) and
        not re.search(r"[,;?\\%]", s)
    )


def not_empty_string(s):
    """A string that can't be empty."""
    return isinstance(s, str) and len(s) > 0


def github_username(s):
    """Is this a valid GitHub username?"""
    # Usernames can have "[bot]" at the end for bots.
    suffixes = ["[bot]", "%5Bbot%5D"]
    for suffix in suffixes:
        if s.endswith(suffix):
            s = s[:-len(suffix)]
            break
    # For Anant, we added a star just to be sure we wouldn't find some other
    # account, so allow a star at the end.
    return re.match(r"^[a-zA-Z0-9_-]+\*?$", s)


ORGS_SCHEMA = Schema(
    Or(
        {
            str: {
                Optional("name"): not_empty_string,
                "agreement": Or("institution", "none"),
                Optional("contractor"): bool,
                Optional("committer"): bool,
                Optional("internal-ghorgs"): [str],
                Optional(Or("contact", "contact1", "contact2")): {
                    "name": not_empty_string,
                    "email": valid_email,
                },
            },
        },
        {},
    )
)


# Prevent duplicate keys in YAML.
# Adapted from https://gist.github.com/pypt/94d747fe5180851196eb
# from https://bitbucket.org/xi/pyyaml/issues/9/ignore-duplicate-keys-and-send-warning-or

def mapping_constructor(loader, node, deep=False):
    """Prevent duplicate keys and return an OrderedDict."""

    mapping = collections.OrderedDict()
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        value = loader.construct_object(value_node, deep=deep)
        if key in mapping:
            raise ConstructorError("while constructing a mapping", node.start_mark,
                                   "found duplicate key (%s)" % key, key_node.start_mark)
        mapping[key] = value

    return mapping


yaml.SafeLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping_constructor)


# The public functions.

def validate_orgs(filename):
    """
    Validate that `filename` conforms to our orgs.yaml schema.
    """
    with open(filename) as f:
        orgs = yaml.safe_load(f)
    ORGS_SCHEMA.validate(orgs)
    # keys should be sorted.
    assert_sorted(orgs, "Keys in {}".format(filename))


def validate_salesforce_export(filename, encoding="cp1252"):
    """
    Validate that `filename` is a Salesforce export we expect.
    """
    with open(filename, encoding=encoding) as fcsv:
        reader = csv.DictReader(fcsv)
        assert reader.fieldnames == [
            "First Name", "Last Name", "Number of Active Ind. CLA Contracts",
            "Title", "Account Name", "Number of Active Entity CLA Contracts", "GitHub Username",
        ]
        for row in reader:
            acct = row["Account Name"]
            if acct == "Opfocus Test":
                # A bogus entry made by the vendor. skip it.
                continue
            username = row["GitHub Username"]
            assert github_username(username), f"GitHub Username is not valid: {username}"


def assert_sorted(strs, what):
    """
    Assert that a sequence of strings is sorted.

    Args:
        strs (iterable of strings): the strings that must be sorted.
        what (str): a description of what these are, for the failure message.
    """
    strs = list(strs)
    sstrs = sorted(strs)
    if strs == sstrs:
        return

    lines = difflib.Differ().compare(strs, sstrs)
    out_of_place = set(ln[2:] for ln in lines if ln.startswith(("-", "+")))
    msg = "{} must be sorted. These are out of place: {}".format(
        what, ", ".join(out_of_place)
    )
    assert False, msg
