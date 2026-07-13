# Releasing causal-emergence-zoo

Releases are built from a GitHub release tag and published with PyPI Trusted
Publishing. No long-lived PyPI API token is stored in the repository.

## One-time PyPI setup

Before the first public release, configure a **pending publisher** in the PyPI
account that will own `causal-emergence-zoo`:

| PyPI field | Value |
| --- | --- |
| PyPI project name | `causal-emergence-zoo` |
| Owner | `tsauce32` |
| Repository | `causal-emergence-zoo` |
| Workflow filename | `publish.yml` |
| Environment name | `pypi` |

Use the PyPI project's **Publishing** settings and select GitHub as the trusted
publisher. The workflow's GitHub environment has the same name, `pypi`.

## Release checklist

1. Update the version and changelog, then merge the release branch after CI is
   green.
2. In GitHub, create a release with a tag exactly matching `v<project.version>`
   (for example, `v0.2.1`).
3. Publishing runs automatically from `.github/workflows/publish.yml`. It builds
   both a wheel and source distribution, installs the wheel into a clean virtual
   environment, then uses PyPI's OpenID Connect trusted publisher.
4. Confirm the new version appears on PyPI and install it in a separate clean
   environment with `python -m pip install causal-emergence-zoo`.

If the initial PyPI job is rejected, check the pending-publisher values above
and rerun the GitHub release workflow; do not add a long-lived upload token as a
workaround.
