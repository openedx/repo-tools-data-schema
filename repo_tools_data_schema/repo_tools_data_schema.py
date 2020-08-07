"""
Functions for validating the schema of repo-tools-data.
"""

import collections
import datetime
import pathlib
import re

import yaml
from schema import And, Optional, Or, Schema, SchemaError
from yaml.constructor import ConstructorError


def valid_agreement(s):
    """Is this a valid "agreement" value?"""
    return s in ['institution', 'individual', 'none']


def valid_email(s):
    """Is this a valid email?"""
    return isinstance(s, str) and re.match(r"^\S+@\S+\.\S+$", s)


def valid_org(s):
    """Is this a valid GitHub org?"""
    return isinstance(s, str) and re.match(r"^[^/]+$", s)


def valid_repo(s):
    """Is this a valid repo?"""
    return isinstance(s, str) and re.match(r"^[^/]+/[^/]+$", s)


def existing_person(s):
    """Is this an existing person in people.yaml?"""
    return isinstance(s, str) and s in ALL_PEOPLE


def not_empty_string(s):
    """A string that can't be empty."""
    return isinstance(s, str) and len(s) > 0


def check_institution(d):
    """If the agreement is institution, then we have to have an institution."""
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


PEOPLE_SCHEMA = Schema(
    {
        And(github_username, not_data_key): And(
            {
                'name': not_empty_string,
                'email': valid_email,
                'agreement': valid_agreement,
                Optional('institution'): not_empty_string,
                Optional('is_robot'): bool,
                Optional('jira'): not_empty_string,
                Optional('comments'): [str],
                Optional('other_emails'): [valid_email],
                Optional('before'): {
                    datetime.date: And(
                        {
                            'agreement': valid_agreement,
                            Optional('institution'): not_empty_string,
                            Optional('comments'): [str],
                            Optional('committer'): {
                                Optional('orgs'): [valid_org],
                                Optional('repos'): [valid_repo],
                                Optional('champions'): [existing_person],
                            },
                        },
                        check_institution,
                    ),
                },
                Optional('beta'): bool,
                Optional('contractor'): bool,
                Optional('committer'): {
                    Optional('orgs'): [valid_org],
                    Optional('repos'): [valid_repo],
                    'champions': [existing_person],
                },
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
    nicks = list(orgs)
    assert nicks == sorted(nicks)


def validate_people(filename):
    """
    Validate that `filename` conforms to our people.yaml schema.
    Supporting files are found in the same directory as `filename`.
    """
    people = yaml.safe_load(open(filename))

    global ALL_ORGS, ALL_PEOPLE
    with open(pathlib.Path(filename).parent / "orgs.yaml") as orgsf:
        ALL_ORGS = set(yaml.safe_load(orgsf))

    ALL_PEOPLE = set(people)

    PEOPLE_SCHEMA.validate(people)
    # keys should be sorted.
    nicks = list(people)
    assert nicks == sorted(nicks)
