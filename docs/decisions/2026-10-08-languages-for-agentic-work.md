# Decision Record 2026-10-08: Languages for Agentic Work

## Status timeline

2026-10-08: Proposed by Claude, at JC's request, after a project thread on whether feedback is the bottleneck for agentic development

2026-10-08: Accepted by JC: don't build a new language for agents, and prefer Rust

## Objective Context

### Simple, lovable, complete must haves

#### Functional

Pick the languages agents write project code in, by what makes agents succeed: fast, precise feedback, and a language models already know well.

Say where battle-tested code (TLS, crypto, time zones, Unicode, parsing untrusted input) comes from, since agents can write ordinary plumbing but shouldn't write those.

#### Non-functional

Every claim cites a source, and claims that are judgment rather than evidence say so.

### Nice to haves

#### Functional

Measure the choice with this repo's own [evals](../../evals/README.md) once the live harness runs.

#### Non-functional

### Avoid out of scope runaway rabbit hole risks

#### Functional

Designing and building a new programming language for agents.

Rewriting existing projects in Rust.

#### Non-functional

## Decision

1. **No new language for agents.**
   [SPEC-2026-10-04-language](../../projects/language/specs/SPEC-2026-10-04-language.md) is dropped.
   The cost that can be measured is unfamiliarity: in a study across Python, Java, Rust, and OCaml, agents spent 1.28–1.69× Python's tokens in OCaml, and 92% of failed OCaml attempts were compile errors, while pass rates were similar ([Wu, Anderson, and Guha 2026](https://arxiv.org/abs/2607.22807)).
   A new language starts with no training data at all, so it would sit below OCaml on that axis, whatever its design.
2. **Rust is the preferred language for new non-browser code** (command line tools, back ends, libraries, and anything other languages call):
   - The compiler catches most mistakes before tests run.
     In one evaluation of models writing TypeScript, 94% of compile errors came from failing type checks, and constraining generation with types cut compile errors by more than half ([Mündler et al. 2025](https://arxiv.org/abs/2504.09246)), so a strict checker is most of the feedback loop.
   - Memory safety without a garbage collector, data races rejected at compile time, and no null (`Option` and exhaustive matching).
   - Direct C ABI interop in both directions.
   - Costs: slower builds than Go, 1.07–1.57× Python's tokens in the study above, and TLS and Unicode come from crates rather than the standard library.
3. **Go is the alternative** when build speed or zero dependencies matters more than those guarantees.
   Its standard library covers HTTP, TLS, crypto, JSON, and SQL, and its crypto core was audited by Trail of Bits in 2025 with one low-severity finding ([Go blog](https://go.dev/blog/tob-crypto-audit)) and holds FIPS 140-3 certificate #5247 ([Go docs](https://go.dev/doc/security/fips140)); TLS itself was out of that audit's scope.
4. **TypeScript stays for browser apps and Python with uv for data and ML**, as in [Projects in ageone](2026-09-30-projects-in-ageone.md), both run under their strict type checkers.
5. **Battle-tested pieces come from audited libraries, never agent-written code:**
   TLS from rustls on aws-lc-rs (FIPS 140-3 certificate #4816, [rustls docs](https://docs.rs/crate/rustls/0.23.43/source/src/manual/fips.rs)), Unicode from [ICU4X](https://blog.unicode.org/2025/10/icu4x-21-released.html), and crypto from the Rust or Go libraries above, or libsodium through the C ABI, kept updated (its last independent audit was in 2017, and CVE-2025-69277 was patched in January 2026 per [Ubuntu](https://lists.ubuntu.com/archives/ubuntu-security-announce/2026-January/010073.html)).
   Agents may write small, testable plumbing themselves (JSON, argument parsing, retries, config) instead of adding a dependency; this is judgment, not a measured result.
6. **Annotate boundaries, infer locals.**
   Inferred types are as exact as written ones, but an agent reading code can't see them without a lookup.
   Rust's rule, types required on function signatures and inferred inside bodies, gives agents exact types where they call or change code; avoid relying on whole-program inference.

### High-level C4(context/container/component/code) diagram

### Choices and Tradeoffs/Risks

- Common Lisp, as argued in [Why Common Lisp is now the best programming language](https://www.vivienhenz.com/common-lisp) ([HN discussion](https://news.ycombinator.com/item?id=49973598)): a live image removes rebuilds, but the claim rests on the author's experience, its standard has no threads, sockets, or networking ([HyperSpec contents](https://www.lispworks.com/documentation/HyperSpec/Front/Contents.htm)), and models know it less well.
- Rust over Go: stronger guarantees and interop, paid for in build time, tokens, and dependencies for TLS and Unicode.
- Dropping the language spec gives up a language shaped exactly to the repo's wishes (homoiconic, effect-typed); the spec stays in the repo as a record of that design.
- Feedback speed is not the whole bottleneck: model thinking time often outweighs build time, so a fast checker matters more than a REPL.

### Dependencies

Rust isn't in `devenv.nix` or the [project template](2026-10-04-project-template.md) yet; the first Rust project adds it.

### Interfaces

## Key Results and retrospective feedback
