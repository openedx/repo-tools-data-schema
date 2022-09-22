"""
Functions for validating the schema of repo-tools-data.
"""

import collections
import csv
import datetime
import difflib
import functools
import pathlib
import re

import requests
import yaml
from schema import And, Optional, Or, Schema, SchemaError
from yaml.constructor import ConstructorError


def valid_agreement(s):
    """Is this a valid "agreement" value?"""
    return s in ['institution', 'individual', 'none']


def valid_email(s):
    """Is this a valid email?"""
    return bool(
        isinstance(s, str) and
        re.search(r"^[^@ ]+@[^@ ]+\.[^@ ]+$", s) and
        not re.search(r"[,;?\\%]", s)
    )


@functools.lru_cache(maxsize=None)
def github_repo_exists(full_name):
    resp = requests.get(f"https://api.github.com/repos/{full_name}")
    if resp.status_code != 200:
        raise SchemaError(f"GitHub responded with {resp.status_code} for repo {full_name}")
    repo_actual_name = resp.json()["full_name"]
    if repo_actual_name != full_name:
        raise SchemaError(f"Repo {full_name} is actually at {repo_actual_name}")
    return True

def valid_org(s):
    """Is this a valid GitHub org?"""
    return isinstance(s, str) and re.match(r"^[^/]+$", s)


def valid_repo(s):
    """Is this a valid repo?"""
    return (
        isinstance(s, str) and
        re.match(r"^[^/]+/[^/]+$", s) and
        github_repo_exists(s)
    )


def existing_person(s):
    """Is this an existing person in people.yaml?"""
    return isinstance(s, str) and s in ALL_PEOPLE


def not_empty_string(s):
    """A string that can't be empty."""
    return isinstance(s, str) and len(s) > 0


def check_institution(d):
    """If the agreement is institution, then we have to have an institution."""
    if "agreement" in d:
        if d['agreement'] == 'institution':
            if 'institution' in d:
                if d['institution'] not in ALL_ORGS:
                    raise SchemaError("Institution {!r} isn't in orgs.yaml: {}".format(d['institution'], d))
        if d['agreement'] == 'none':
            if 'institution' in d:
                raise SchemaError("No-agreement should have no institution")
    return True


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


def not_data_key(s):
    """Make sure the GitHub name is not a data line at the wrong indent."""
    return s not in [
        'name', 'email', 'agreement', 'institution', 'jira',
        'comments', 'other_emails', 'before', 'beta', 'committer', 'email_ok',
    ]


def one_of_keys(*keys):
    """Checks that at least one key is present (not exclusive OR)"""
    def _check(d):
        if sum(k in d for k in keys) > 0:
            return True
        raise SchemaError("Must have at least one of {}".format(keys))
    return _check


COMMITTER_SCHEMA = Schema(
    Or(
        # "committer: false" means this person is not a committer.
        False,
        # or explain where they are a committer:
        And(
            {
                Optional('orgs'): [valid_org],
                Optional('repos'): [valid_repo],
                Optional('champions'): [existing_person],
                Optional('branches'): [not_empty_string],
            },
            # You have to specify at least one of orgs, repos, or branches:
            one_of_keys("orgs", "repos", "branches"),
        ),
    ),
)

PEOPLE_SCHEMA = Schema(
    {
        And(github_username, not_data_key): And(
            {
                'name': not_empty_string,
                'email': valid_email,
                'agreement': valid_agreement,
                Optional('institution'): not_empty_string,
                Optional('is_robot'): True,
                Optional('jira'): not_empty_string,
                Optional('comments'): [str],
                Optional('other_emails'): [valid_email],
                Optional('before'): {
                    datetime.date: And(
                        {
                            Optional('agreement'): valid_agreement,
                            Optional('institution'): not_empty_string,
                            Optional('comments'): [str],
                            Optional('committer'): COMMITTER_SCHEMA,
                        },
                        check_institution,
                    ),
                },
                Optional('beta'): bool,
                Optional('contractor'): bool,
                Optional('committer'): COMMITTER_SCHEMA,
                Optional('email_ok'): bool,
            },
            check_institution,
        ),
    }
)

ORGS_SCHEMA = Schema(
    {
        str: {
            Optional("name"): not_empty_string,
            "agreement": Or("institution", "none"),
            Optional("contractor"): bool,
            Optional("committer"): bool,
            Optional("internal"): bool,
            Optional(Or("contact", "contact1", "contact2")): {
                "name": not_empty_string,
                "email": valid_email,
            },
        },
    }
)


def color(s):
    return re.match(r"^[a-fA-F0-9]{6}$", s)


LABELS_SCHEMA = Schema(
    {
        str: Or(
            # A label we don't want:
            {
                "delete": True,
            },
            # A label we want:
            {
                "color": color,
                Optional("description"): str,
            },
        ),
    },
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

def validate_labels(filename):
    """
    Validate that `filename` conforms to our labels.yaml schema.
    """
    labels = yaml.safe_load(open(filename))
    LABELS_SCHEMA.validate(labels)


def validate_orgs(filename):
    """
    Validate that `filename` conforms to our orgs.yaml schema.
    """
    orgs = yaml.safe_load(open(filename))
    ORGS_SCHEMA.validate(orgs)
    # keys should be sorted.
    assert_sorted(orgs, "Keys in {}".format(filename))


def validate_people(filename):
    """
    Validate that `filename` conforms to our people.yaml schema.
    Supporting files are found in the same directory as `filename`.
    """
    people = yaml.safe_load(open(filename))

    global ALL_ORGS, ALL_PEOPLE
    with open(pathlib.Path(filename).parent / "orgs.yaml") as orgsf:
        org_data = yaml.safe_load(orgsf)
        ALL_ORGS = set(org_data)
        for orgd in org_data.values():
            name = orgd.get("name")
            if name:
                ALL_ORGS.add(name)

    ALL_PEOPLE = set(people)

    PEOPLE_SCHEMA.validate(people)
    # keys should be sorted.
    assert_sorted(people, "Keys in {}".format(filename))


def validate_salesforce_export(filename, encoding="cp1252"):
    """
    Validate that `filename` is a Salesforce export we expect.
    """
    with open(filename, encoding=encoding) as fcsv:
        reader = csv.DictReader(fcsv)
        # fields are:
        # "First Name","Last Name","Number of Active Ind. CLA Contracts","Title","Account Name","Number of Active Entity CLA Contracts","GitHub Username"
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
