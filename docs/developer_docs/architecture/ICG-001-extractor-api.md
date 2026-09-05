# ICG-001: Use LLVM 17 LibTooling for the extractor

- Status: Accepted
- Date: 2026-09-05
- Scope: New semantic extractor only

## Context

The rewrite needs structured records, fields, inheritance/layout, special-member
capabilities, templates including packs, source provenance, comments, and
diagnostics. The first compatibility backend must reproduce flattened inherited
legacy metadata without changing the runtime ABI. Clang objects must remain
inside one C++17 extractor process regardless of the frontend API.

The stable libclang C API was preferred if it could satisfy this contract without
recovering semantics from type spellings. A focused LLVM 17.0.6 probe exercises
the relevant API in [`tools/icg_capability`](../../../tools/icg_capability/README.md).

## Decision

Implement the single production extractor with LLVM 17 LibTooling using normal
`ASTFrontendAction`, `ASTConsumer`, `RecursiveASTVisitor`, `PPCallbacks`, and
compilation-database APIs. Isolate LLVM APIs in the extractor adapter and emit
only Trick-owned value types through the versioned process boundary.

Do not implement or maintain a libclang production extractor. The capability
probe remains as decision evidence and as a guard against accidentally relying
on C API behavior elsewhere.

## Evidence

| Required fact | LLVM 17 C API observation | Consequence |
|---|---|---|
| Fields and immediate layout | Field offset query succeeded | C API sufficient for this fact |
| Base discovery and virtuality | All four bases and both virtual bases were found | C API sufficient for identity/virtuality |
| Base layout | The field-offset cursor API returned `-1` for every base cursor | Cannot reproduce inherited legacy offsets |
| Explicit special members | Deleted/defaulted default constructors were distinguished | C API sufficient when declarations exist |
| Implicit special members | `ImplicitSpecial` exposed no constructor cursor | Cannot reproduce current constructibility logic |
| Type/integral template arguments and partial specializations | Structurally exposed with exact integral value | C API sufficient for these cases |
| Variadic specialization | `Pack<int, double>` appeared as one opaque pack argument | Cannot build the required structured pack graph |
| Comments, annotations, friends/access, abstract/anonymous records, bitfields | Focused cases succeeded; dependent width returned an explicit negative query | C API sufficient with an unknown-width state |

The blockers are independently material. Base layout is required by the first
legacy backend, implicit construction controls allocation thunk emission, and
pack elements are required by the owned type graph. Type-spelling parsing would
violate the structured-semantics requirement. Moving immediately to runtime v2
would couple the extractor rewrite to a separate runtime migration.

## Consequences

- The adapter uses LLVM's C++ API and needs explicit adapters when a supported
  LLVM upgrade breaks source compatibility.
- The owned IR and process boundary contain that source/API churn.
- The extractor target must compile as C++17 with GCC 8.5 and the maintained
  GCC 12 lane; this remains a separate blocking probe.
- A later runtime metadata design may reduce the need for raw base offsets, but
  that does not reopen this decision unless the full required capability suite
  changes.
