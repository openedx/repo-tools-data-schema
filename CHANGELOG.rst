Change Log
----------

..
   All enhancements and patches to repo_tools_data_schema will be documented
   in this file.  It adheres to the structure of https://keepachangelog.com/ ,
   but in reStructuredText instead of Markdown (for ease of incorporation into
   Sphinx documentation and the PyPI description).

   This project adheres to Semantic Versioning (https://semver.org/).


2023-05-30
~~~~~~~~~~

* Make it valid for ORGS, LABELS, and PEOPLE to be empty. This was prompted
  because we actually want LABELS to be empty as an intermediate step towards
  removing label creation from openedx-webhooks.

2023-03-02
~~~~~~~~~~

* Added a ``internal-ghorgs`` setting to represent the more complex world we
  live in now after the decoupling.  Different institutions are "internal" to
  different GitHub organizations.

2022-09-22
~~~~~~~~~~

* Don't validate orgs using orgs.yaml in the saleseforce export csv.

2020-08-07
~~~~~~~~~~

* First release.
