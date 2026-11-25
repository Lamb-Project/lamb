# Knowledge packs

A knowledge pack is the guidance LAMB LEGATUS works with: its persona, its vocabulary in four
languages and its guides (workflow recipes). A pack is advice. What a person may do is decided
by LAMB (role, ownership, approvals), and a command LAMB supports runs whether or not a guide
covers it.

## Lines, not versions

An organization follows a **line**, never an exact version. `lines.yaml` names the pack each
line holds:

| Line | What it is | Who sees it |
|---|---|---|
| `stable` | The pack shipped with this LAMB version | Everyone; the default |
| `legacy` | The stable packs of the two previous LAMB versions | Everyone, when present |
| `rc` | One release candidate, or none | Organizations in development mode |
| `beta` | The pack being written, or none | Organizations in development mode |

At most five packs are installed. A new beta replaces the previous beta and a new candidate
replaces the previous candidate; git keeps their history. An empty line follows `stable`.

## Layout

- `lines.yaml`: which version each line holds. Change it with the build commands, not by hand.
- `lamb-default/`: the workspace, where the beta is written.
- `releases/lamb-default/<version>/`: the frozen packs (stable, legacy, rc). Their content is
  verified against the hashes in their manifest every time they are loaded.
- `ABOUT.md` in each pack: what the version is for and what changed, shown to organization
  administrators with its `summary` line. It is written for people, is never sent to the
  model and is the one file outside the content hashes. Its guide list is generated.

## Commands

Run from `backend/`:

```sh
python -m lamb.aac.pack_build                    # check the workspace and every installed pack
python -m lamb.aac.pack_build --write            # regenerate glossaries, guide list and hashes
python -m lamb.aac.pack_build --start 2.1        # begin a version: the workspace becomes 2.1-beta.1
python -m lamb.aac.pack_build --bump             # a new beta replaces the previous one
python -m lamb.aac.pack_build --promote rc       # the beta becomes the release candidate
python -m lamb.aac.pack_build --promote stable   # the candidate becomes stable; the old stable becomes legacy
```

Stable packs are numbered with two numbers (`2.0`, `2.1`), pre-releases as `2.0-beta.4` and
`2.0-rc.1`. The stable pack changes with a LAMB release. `--write` needs the frontend locale
files and the knowledge-base plugin sources of the repository checkout.

## Guides that are missing

`python -m lamb.aac.unguided` lists, from the private session traces, the commands that ran
without a guide and how they ended. The ones that recur and succeed are the candidates for the
next guides.
