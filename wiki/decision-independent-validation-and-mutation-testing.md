# Decision: check our own numbers independently, and break the code on purpose

Date: 2026-11-18
Status: Decided

## In one sentence

A second reviewer who did not write the code recomputes the results from raw inputs with different code, and we also inject deliberate bugs to see whether our tests notice.

## What we decided

- Every item needs a review by someone other than its author. For each new statistic, an independent pass rebuilds the headline numbers from raw downloads.
- Mutation testing: change one line of the code on purpose (a "mutant"), run the test suite, and record whether any test fails. A mutant that no test catches "survives" and shows a gap.
- Findings are ranked by severity and fixed or recorded as deviations.
- Round 1 is dated 2026-11-18, on the SPY slice. Fixes are in progress as of that date.

## Why

Tests written by the author often check what the author expected. The sources state the practice, not the alternatives, so the rejections below are our reading. We rejected relying on the author's own tests because a wrong convention can pass every test that shares it. We rejected "read the code and trust it" because many errors are numerical and invisible on reading. We rejected counting passing tests as evidence, because a high pass rate says nothing about whether the tests are sensitive.

## How it works

- Round 1 rebuilt the SPY report from raw inputs with a separate parser, separate date alignment and plain statsmodels. Headline numbers matched to about 1e-7, and the return and risk identities held to about 1e-16.
- 17 mutants were tried. 12 were caught and 5 survived. Caught examples: HAC lag rule changed by one, the one-day lag on timing betas removed, risk-free rate not subtracted, 365 days instead of 252, window off by one.
- Survivors: a risk-sentence boundary, an audit tolerance made 10 times too loose, a missing square root in the condition number, an alpha-sentence boundary, and a correlation threshold moved from 0.6 to 0.7. All were tested only far from the boundary, or relative to the constant under test.
- The fix: test exactly at boundaries and pin constants to literal numbers from the specification.

## What it costs us

- Review needs a second person and time; each mutant needs a full test run (the default suite took about 73 seconds on 2026-11-18).
- 17 mutants is a small sample. Survivors prove gaps; caught mutants do not prove completeness.
- The review found real problems before release: crashes on odd inputs, a silent duplicate-date drop, and a gap between the audit code and the specification.
- Which fixes are complete is not recorded in the sources as of 2026-11-18.

## What would change our mind

A cheaper independent check with the same power (for example property-based tests that catch the surviving mutants), or evidence that review rounds find nothing new across several modules.

## Sources

- [docs/validation/spy-slice-validation.md](../docs/validation/spy-slice-validation.md), sections 1, 4 and 6.
- [docs/test-oracle.md](../docs/test-oracle.md): the tests that fix each number.
- [docs/PLAN.md](../docs/PLAN.md), Definition of Done.
- [CODING_STANDARDS.md](../CODING_STANDARDS.md).

## Related decisions

- [Thin slice on SPY first](decision-thin-slice-on-spy-first.md)
- [SPY timing noise and the quality gate](decision-spy-timing-noise-and-the-quality-gate.md)
- [Branches and pull requests](decision-branches-and-pull-requests.md)
