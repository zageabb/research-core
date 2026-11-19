# UDA V2 review — Research Core (DEV-020)

**Review-only library candidate.** No service, port, proxy or production activation.

Source inspection: `README.md` describes research-core as a Python library
consumed by Tender Designer, Internet Pricing and Should-Cost Intelligence, with
no standalone listener. `pyproject.toml` uses setuptools, requires Python
>=3.10 and currently identifies version 0.2.1. Consumers must pin the package
to a reviewed Git SHA/tag; do not change their dependency pins as a side effect
of approving this manifest.

The draft declares a wheel build using `python3 -m build --wheel`.
The `build` module is a build-environment prerequisite, not declared in the
repository's dependencies: independently confirm a disposable Python build
environment supplies it, and verify the produced wheel contains the intended
`research_core` package and no secrets.

Remaining checks:
- [ ] Canonical UDA schema and semantic validator.
- [ ] Independent wheel build with pinned source revision, artifact/hash audit
      and Python tests in a disposable environment.
- [ ] Verify downstream consumer dependency pins and packaging compatibility.
- [ ] Confirm registry categorization and library install target read-only.
- [ ] Separate owner approval for any package installation/consumer change.

No runtime, secret, systemd, database migration or port has been invented.
