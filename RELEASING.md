# Releasing

A release touches more places than it looks like, and two of the four bugs in
[PLAN.md §28–§29](PLAN.md) were caused by missing one of them. This is the list.

## Where a version is declared

Three files, and they must agree. A fourth used to, and that is what broke:
`__init__.py` held a literal that drifted from `pyproject.toml` through two
releases, so `sla --version` reported `0.1.0` while `0.2.1` was published. It now
reads from installed metadata, so **do not reintroduce a literal** — there is a
test that fails if you do.

| File | What it versions |
|---|---|
| `pyproject.toml` | the Python package, and therefore `sla --version` |
| `.claude-plugin/plugin.json` | the Claude Code plugin |
| `.claude-plugin/marketplace.json` | the marketplace entry for the plugin |

`tests/test_packaging.py::test_every_declared_version_agrees` checks all three.
`claude plugin tag` checks the latter two against each other and knows nothing
about Python, which is exactly how the drift survived.

## Before you bump

```bash
.venv/bin/python -m pytest          # all green
sla doctor                          # no FAIL lines, no skew
```

Push first and let CI finish. It runs the suite on Linux, macOS and Windows, the
suite against the *installed* wheel, and a `twine check --strict` of the
distribution — a listing that fails to render is otherwise only discoverable
after publishing, which cannot be undone.

Add the `CHANGELOG.md` entry **before** tagging, not after. `claude plugin update`
reports "0.2.1 → 0.2.2" and the changelog is the only way anyone learns what that
means.

## The release

```bash
# 1. bump all three files to the same number
# 2. verify they agree, then commit
.venv/bin/python -m pytest tests/test_packaging.py
git commit -am "chore: release X.Y.Z"

# 3. tag. This is the format the existing tags use.
git tag "self-learning-agent--vX.Y.Z"
git push origin main --tags
```

## PyPI

The name `self-learning-agent` is unregistered on both PyPI and TestPyPI.

**Publishing is irreversible.** A filename on an index can never be reused, even
after deleting the release — so a bad `0.3.0` burns `0.3.0` permanently. Rehearse
on TestPyPI first.

### Preferred: Trusted Publishing, so no token is ever stored

`.github/workflows/release.yml` publishes on a matching tag using OIDC, which
means there is no API token in the repository or on your machine. It is inert
until you configure the publisher, so pushing it changes nothing on its own.

One-time setup at <https://pypi.org/manage/account/publishing/>:

| Field | Value |
|---|---|
| PyPI project name | `self-learning-agent` |
| Owner | `Soham-1827` |
| Repository name | `Self-Learning-Agent-Claude` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

Then create a GitHub environment called `pypi` in the repository settings. After
that, pushing a `self-learning-agent--v*` tag publishes.

### Rehearsal on TestPyPI

```bash
rm -rf dist && uv build
uvx twine check --strict dist/*
uvx twine upload --repository testpypi dist/*
# then, in a throwaway venv, prove the published artifact works:
uv venv --python 3.12 /tmp/t && uv pip install --python /tmp/t/bin/python \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple/ self-learning-agent
/tmp/t/bin/sla --version && /tmp/t/bin/sla doctor
```

### Manual publish, if you would rather not use OIDC

```bash
rm -rf dist && uv build
uvx twine check --strict dist/*
uvx twine upload dist/*     # username __token__, password the pypi-… token
```

## After publishing

```bash
claude plugin marketplace update self-learning-agent
claude plugin update self-learning-agent
sla doctor                  # the plugin line should match the CLI line
```

Then verify from the outside rather than from the checkout — §28's lesson. In a
clean environment:

```bash
uv tool install self-learning-agent
sla --version               # must equal the number you just tagged
sla doctor
```

Finally, swap the install line in `README.md` from the git URL to
`uv tool install self-learning-agent`, and **leave the git URL documented** as
the way to install an unreleased commit.
