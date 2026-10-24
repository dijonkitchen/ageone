# SPEC-2026-10-04-language: A Programming Language from First Principles

Dropped on 2026-10-08 by [Languages for Agentic Work](../../../docs/decisions/2026-10-08-languages-for-agentic-work.md): a new language starts with no training data, which costs agents more than any design gains, so new code prefers Rust instead.
The spec stays as a record of the design.

A new programming language, designed from first principles for both people and AI agents to write, read, and change safely.
It combines things no mainstream language has together:

- memory control like Rust: no garbage collector, deterministic cleanup, no data races;
- a mostly pure functional core: immutable values, minimal mutable state, and side effects visible in types;
- syntax simple enough to read like pseudocode, where code is also plain data the language can read and build (homoiconic);
- type inference and safety like ML: types rarely written, no null, every case handled;
- tooling and errors made for AI agents as well as people;
- compatibility with libraries that already exist, so a new language doesn't mean starting from an empty ecosystem.

The language's name is chosen in its first decision record; until then the project lives in `projects/language/`.

## Functional requirements

### Design document

- A language design document in `projects/language/docs/` that starts from the goals above and justifies each feature by them, citing the prior art it borrows from or rejects (Rust, OCaml, Standard ML, Haskell, Go, Koka, Roc, Lean 4, Clojure, jank, Carp, Coalton, Racket and Rhombus, Elixir, Julia, Unison, Hylo/Val, Vale, Austral, Gleam, Zig).
- A "why not use an existing language" section that tests the closest languages against the goals and says what each misses, so the project only goes ahead if none is close enough:
  Clojure and jank (code as data and minimalism, but dynamic types and a garbage collector), Carp (a typed Lisp with ownership and no garbage collector, the closest match), Coalton (ML-style types inside Common Lisp, with a garbage collector), and Roc, Koka, and Lean 4 (pure and typed with in-place reuse, but code isn't plain data).
  It also weighs building on one of them, such as a Clojure dialect implemented in Rust, against starting fresh.
- Each major choice is its own decision record in `projects/language/docs/decisions/`: memory model, purity and effects, syntax and code as data, type system, error handling, agent tooling, interop, and implementation strategy.
- A short language reference with the grammar and the typing, effect, and ownership rules, precise enough that a second implementation could follow it.

### Memory control, like Rust

- No garbage collector and no reference counting by default: every value has one owner and is freed deterministically when its owner goes out of scope.
- Moves and borrows are checked at compile time: a value can't be used after it is moved, and a borrowed value can't change while it is borrowed.
- Lifetimes are inferred: ordinary code never writes a lifetime annotation.
  The design weighs Rust's borrow checker against simpler models that need no annotations, such as mutable value semantics with second-class references (Hylo/Val), regions, or compile-time reference counting with reuse (Perceus in Koka and Roc, Lean 4), and records why it picks one.
- Programmers can choose where values live (stack or heap) and control layout when they need to, with an explicit `unsafe` escape hatch for raw memory that safe code can't reach.
- Opt-in shared ownership (such as a reference-counted box) for the cases single ownership can't express, visible in the type.

### Mostly pure, with minimal mutable state

- Values are immutable, and functions are pure by default: the same arguments always give the same result, with no hidden side effects.
- Updates are functional (a new value with one field changed), and when the old value is uniquely owned the compiler reuses its memory in place, so pure code runs as fast as mutating code ("functional but in place", as in Koka, Roc, and Lean 4).
  Ownership is what makes this safe: the compiler knows when nothing else can see the old value.
- Where mutation reads better, such as a loop accumulator, it is local to a function and can't be observed from outside it.
- No global mutable state.
- Side effects (input and output, failure, randomness, time, foreign calls) are tracked in types, as effect rows (Koka) or capabilities passed as arguments; the effects decision record picks one.
  Effects are inferred inside a module, a pure function can't call an effectful one without saying so, and tests can swap an effect's handler for a fake.

### Simple, readable syntax, with code as data

- Minimal, like Go: few keywords, one obvious way to write each construct, no operator overloading surprises, and a bias toward leaving features out.
  A feature joins only when the problems it solves outweigh the complexity every reader then pays for, and the design document keeps a list of features left out and why, as Go's FAQ does.
- Reads top to bottom and left to right: expression-oriented, with a pipeline operator for chaining calls, and no semicolons or type noise in ordinary code.
- Ownership and effects are visible but quiet: a reader can tell where a value moves and what a function can do without knowing the rules.
- Homoiconic: every program parses into a small tree of plain data (lists, symbols, and literals) that the language itself can build, inspect, transform, and print, and printing a tree then parsing it gives the same tree back.
  Quoting turns code into data, so programs, tools, and agents edit code as structured data rather than text.
- The syntax decision record weighs plain S-expressions (Lisp, Clojure), which are homoiconic but less familiar, against a readable surface syntax that maps one-to-one onto the data tree (Rhombus's shrubbery notation, Elixir's quoted forms, Julia's expressions, Dylan), and picks the one that best serves readability and code as data together.
- Error messages explain the problem in plain words, point at the code, and suggest a fix, especially for ownership and effect errors.

### Type inference and safety, like ML

- Hindley-Milner style inference with generics: local variables and private functions need no type annotations.
  Public function signatures, including their effects, are written out, so a module's interface reads on its own and compiles separately; the design records whether that holds.
- Algebraic data types (records and tagged unions) with exhaustive pattern matching: a missing case is a compile error.
- No null: optional values are an `Option` type, and failures are a `Result` type with a short way to pass errors up, instead of exceptions.
- Traits or type classes for shared behavior, resolved at compile time.
- Safe code has no undefined behavior: bounds are checked, integer overflow is an error rather than a silent wrap, and data races can't compile.

### Good for AI agents

- Fits in a prompt: the whole language reference, with examples, ships as one plain-text file small enough to give an agent in its context, and the standard library's signatures can be listed the same way.
- Local reasoning: no implicit conversions, no global state, and explicit imports, so a function's body and signature say everything it can do, and an agent can change one function without reading the whole program.
- One canonical format, like `gofmt`: the formatter has no options, ships with the language, and is the printer of the code tree, so every program has one layout, style is never debated, and agents' diffs stay minimal.
  CI rejects unformatted code.
- One standard tool, like the `go` command: a single command line tool builds, runs, formats, tests, documents, and lints code, with conventions instead of configuration files (where tests and docs live, how a project is laid out).
  It also evaluates an expression, shows the type at a location, and lists a module's definitions, in compact output an agent can parse cheaply.
- Token-lean output, following the repo's [Agent Tool Interfaces](../../../docs/decisions/2026-09-27-agent-tool-interfaces.md) record rather than defaulting to JSON, which spends tokens repeating keys and quotes (pretty JSON cost about 2.7 times as many tokens as CSV in that record's sample): one line per item by default, such as `file:line:col: error E0042: message` for errors (the shape models have seen most from other compilers), CSV for lists, and `key: value` lines for single records.
  The output stays short by default, with counts up front and a flag for the full detail, and `--json` gives NDJSON for scripts.
  Because the language is homoiconic, nested results such as a code tree print in the language's own data notation, which the tool can read back.
  The agent tooling decision record measures the chosen formats with [`experiments/formats`](../../../experiments/README.md), adding a case for reading and acting on compiler errors.
- Structured errors: each error has a stable code, a location, a plain explanation, and, where possible, a suggested fix as a code edit an agent can apply, all in the compact one-line format above with the fix as a unified diff.
- Fast feedback: checking a changed file returns in well under a second, so agents can check after every edit.
- Executable examples: examples in doc comments run as tests, so documentation an agent reads stays correct.
- Deterministic: the same source always builds and runs the same way, and pure functions can be tested without setup.

### Compatible with existing libraries

- Calls libraries written in other languages through the C ABI, the one interface nearly every language and operating system shares, and exports its own functions through it so other languages can call in.
- Bindings are generated from C headers rather than written by hand, and the C types map to the language's own types (pointers, structs, enums, nullable pointers as `Option`).
- Foreign calls are `unsafe` and effectful at the boundary only: each binding can be wrapped once in a safe API that states ownership (who frees what) and effects in its types, so callers never see raw pointers.
- Reaches the two richest ecosystems near this language's niche: Rust crates (through their C ABI, or a generated bridge like [cxx](https://cxx.rs) or [Diplomat](https://github.com/rust-diplomat/diplomat)) and C++ libraries (through a C wrapper).
  The interop decision record weighs these against compiling to a platform with a large library ecosystem of its own (WebAssembly components, the JVM, .NET, or Python extension modules), and records which the implementation supports first.
- The implementation strategy is chosen with interop in mind: compiling through C, LLVM, or Cranelift makes C ABI calls cheap and direct, while a tree-walking interpreter would need a foreign function library such as libffi.

### Implementation

- A compiler or interpreter for a core subset: integers, booleans, strings, lists, functions, closures, records, tagged unions, pattern matching, generics, traits, ownership and borrowing, effects, quoting, `Option`, and `Result`.
- It parses, infers types and effects, checks ownership, and runs the program, reporting errors with source locations.
- Example programs in `projects/language/examples/`, including a linked list, a binary tree, a small text parser, a pure update of a large record or array that runs in place, a program that rewrites another program's code tree, and a program that uses an existing C library (such as SQLite or zlib) through a safe wrapper.
- A test suite of programs that must compile and run with an expected output, and programs that must be rejected with an expected error: use after move, changing a borrowed value, a reference outliving its value, a pure function calling an effectful one, a non-exhaustive match, a type mismatch, and a missing trait.

## Non-functional requirements

- Principled: every feature traces back to one of the goals above, and a feature that serves none is left out.
- Small enough to learn in a day: the core language reference stays short, in the spirit of Go's one-page specification.
- Stable once released: like Go 1's compatibility promise, code that builds keeps building, and the formatter's output doesn't change between versions.
- Fast to build: compile times stay short enough that check-on-every-save never feels slow, as Go treats build speed as a feature.
- Runs in the pinned environment from [SPEC-2026-09-26-make-setup](../../../specs/SPEC-2026-09-26-make-setup.md), with no global installs.
- Out of scope for this spec: a standard library beyond what the examples need, a package manager, macros (the code tree is ready for them), an editor plugin or language server, an optimizer beyond in-place reuse, async or a concurrency runtime, and self-hosting.
  Each can be its own spec later.

## Definition of done

1. The design document and decision records for memory model, purity and effects, syntax and code as data, type system, error handling, agent tooling, interop, and implementation strategy are written, and the first one names the language.
2. The language reference covers the grammar and the typing, effect, and ownership rules of the core subset, and fits in one plain-text file for agents.
3. One command builds the implementation, and the language's single tool runs, formats, and tests a program file, with no configuration file needed.
4. The example programs run and print their expected output without a single type, effect, or lifetime annotation inside function bodies, and the in-place example shows no copy of its data.
5. The test suite passes in CI, including every rejected-program case above, each with a readable error message, a stable code, and the same error in compact form and as `--json`.
6. Every example parses to its code tree and prints back to the same formatted source, and the code-rewriting example runs in CI.
7. An example program calls an existing C library through bindings generated from its headers and wrapped in a safe API, and a C program calls a function exported by the language; both run in CI.
8. An eval in [`evals/`](../../../evals/README.md) gives agents only the language reference and a set of small programming tasks, and compares their pass rate and number of check-and-fix rounds with the same tasks in Rust and OCaml, across the models in `harness/models.json`.
   Running it needs the live harness from [SPEC-2026-09-26-vendor-neutral-ai-harness](../../../specs/SPEC-2026-09-26-vendor-neutral-ai-harness.md).
9. A side-by-side page compares a few example programs with the same programs in Rust and OCaml, showing the line count and annotations each needs.
