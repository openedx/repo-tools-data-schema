import pytest

from repo_tools_data_schema.repo_tools_data_schema import (
    valid_email,
)

@pytest.mark.parametrize("email, ok", [
    ("nedbat@gmail.com", True),
    ("nedbat@gmail.com@bad", False),
    ("nedbat", False),
    ("nedbat@gmail.com,", False),
])
def test_valid_email(email, ok):
    assert valid_email(email) is ok
