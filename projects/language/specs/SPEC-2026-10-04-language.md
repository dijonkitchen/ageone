# SPEC-2026-10-04-language: A Programming Language from First Principles

A new programming language, designed from first principles, that combines three things no mainstream language has together:
memory control like Rust (no garbage collector, deterministic cleanup, no data races), syntax simple enough to read like pseudocode, and type inference and safety like ML (types rarely written, no null, every case handled).

The language's name is chosen in its first decision record; until then the project lives in `projects/language/`.

## Functional requirements

### Design document

- A language design document in `projects/language/docs/` that starts from the goals below and justifies each feature by them, citing the prior art it borrows from or rejects (Rust, OCaml, Standard ML, Haskell, Swift, Hylo/Val, Vale, Koka, Austral, Gleam, Roc, Zig).
- Each major choice is its own decision record in `projects/language/docs/decisions/`: memory model, syntax, type system, error handling, and implementation strategy.
- A short language reference with the grammar and the typing and ownership rules, precise enough that a second implementation could follow it.

### Memory control, like Rust

- No garbage collector and no reference counting by default: every value has one owner and is freed deterministically when its owner goes out of scope.
- Moves, borrows, and mutation are checked at compile time: a value can't be used after it is moved, and a value has either many readers or one writer at a time.
- Lifetimes are inferred: ordinary code never writes a lifetime annotation.
  The design weighs Rust's borrow checker against simpler models that need no annotations, such as mutable value semantics with second-class references (Hylo/Val) or regions, and records why it picks one.
- Programmers can choose where values live (stack or heap) and control layout when they need to, with an explicit `unsafe` escape hatch for raw memory that safe code can't reach.
- Opt-in shared ownership (such as a reference-counted box) for the cases single ownership can't express, visible in the type.

### Simple, readable syntax

- Small: few keywords, one obvious way to write each construct, and no operator overloading surprises.
- Reads top to bottom and left to right: expression-oriented, with a pipeline operator for chaining calls, and no semicolons or type noise in ordinary code.
- Ownership is visible but quiet: moves, borrows, and mutation are marked at the call site in a way a reader understands without knowing the rules.
- Error messages explain the problem in plain words, point at the code, and suggest a fix, especially for ownership errors.

### Type inference and safety, like ML

- Hindley-Milner style inference with generics: local variables and private functions need no type annotations.
  Public function signatures are written out, so a module's interface reads on its own and compiles separately; the design records whether that holds.
- Algebraic data types (records and tagged unions) with exhaustive pattern matching: a missing case is a compile error.
- No null: optional values are an `Option` type, and failures are a `Result` type with a short way to pass errors up, instead of exceptions.
- Traits or type classes for shared behavior, resolved at compile time.
- Safe code has no undefined behavior: bounds are checked, integer overflow is an error rather than a silent wrap, and data races can't compile.

### Implementation

- A compiler or interpreter for a core subset: integers, booleans, strings, functions, closures, records, tagged unions, pattern matching, generics, traits, ownership and borrowing, `Option`, and `Result`.
- It parses, infers types, checks ownership, and runs the program, reporting errors with source locations.
- Example programs in `projects/language/examples/`, including a linked list, a binary tree, a small text parser, and a program that mutates a collection while borrowing from it safely.
- A test suite of programs that must compile and run with an expected output, and programs that must be rejected with an expected error: use after move, two mutable borrows, a reference outliving its value, a non-exhaustive match, a type mismatch, and a missing trait.

## Non-functional requirements

- Principled: every feature traces back to one of the three goals, and a feature that serves none is left out.
- Small enough to learn in a day: the core language reference stays short.
- Runs in the pinned environment from [SPEC-2026-09-26-make-setup](../../../specs/SPEC-2026-09-26-make-setup.md), with no global installs.
- Out of scope for this spec: a standard library beyond what the examples need, a package manager, macros, an editor plugin or language server, an optimizer, async or a concurrency runtime, and self-hosting.
  Each can be its own spec later.

## Definition of done

1. The design document and decision records for memory model, syntax, type system, error handling, and implementation strategy are written, and the first one names the language.
2. The language reference covers the grammar and the typing and ownership rules of the core subset.
3. One command builds the implementation, and one command runs a program file.
4. The example programs run and print their expected output without a single type or lifetime annotation inside function bodies.
5. The test suite passes in CI, including every rejected-program case above, each with a readable error message.
6. A side-by-side page compares a few example programs with the same programs in Rust and OCaml, showing the line count and annotations each needs.
