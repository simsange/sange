<!--
  Thanks for the PR. The questions below help reviewers triage
  fast. Empty sections delay review; one-line answers are fine.
-->

## Summary

<!-- 1-3 sentences. What's the change? Why now? -->

## Motivation

<!--
  Link the issue or discussion that prompted this PR. If there's no
  prior issue, explain the *why* — not the *what* (the diff shows
  the what).
-->

Closes # <!-- issue number, if applicable -->

## Approach

<!--
  Short paragraph on HOW you implemented it. Trade-offs, alternatives
  considered, anything a reviewer should know upfront.
-->

## Testing

<!-- How did you verify this works? -->

- [ ] Unit tests added / updated
- [ ] Integration tests added / updated (if applicable)
- [ ] Manually tested the change end-to-end
- [ ] CI is green on this branch

## Checklist

- [ ] Code follows the project's style (see `CONTRIBUTING.md`)
- [ ] Commit messages follow Conventional Commits 1.0.0
- [ ] Public API changes (breaking + non-breaking) are documented
- [ ] CHANGELOG.md entry added under `## Unreleased` if user-facing
- [ ] If this introduces a new dependency, it's justified in the PR
- [ ] No `--no-verify` was used to bypass hooks
- [ ] Sign-off: `git commit -s` (or DCO bot will request it)

## Breaking changes

<!--
  Does this break public API, output format, or expected behaviour?
  If yes, describe the migration path users will need to take.
  Per Conventional Commits, breaking changes also need a `!` after
  the type in the commit subject + a `BREAKING CHANGE:` footer.
-->

- [ ] This PR is **not** a breaking change.
- [ ] This PR **is** a breaking change (described above + commit
      messages tagged accordingly).

## Reviewer notes

<!--
  Anything you'd like the reviewer to look at first / specifically?
  Areas you're uncertain about?
-->
