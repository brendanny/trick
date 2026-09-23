# Upstream report draft: ICG GNU predefines can disagree with Clang and the model compiler

Status: reproduced locally on 2026-09-23; upstream filing and resolution remain
a prerequisite for C1's general simulation integration. Filing was attempted on
2026-09-23; GitHub rejected issue creation with HTTP 403, "Resource not accessible
by integration". Related upstream discussions: [#1095](https://github.com/nasa/trick/issues/1095)
and [#1553](https://github.com/nasa/trick/issues/1553). This is a Trick frontend
policy issue, independent of output placement and of the icg2 interface.

## Environment

- Linux x86_64, Ubuntu 24.04.3, glibc 2.39.
- GCC/G++ 13.3.0, LLVM/Clang 14.0.6, CMake 3.26.0.
- The local LLVM package was extracted under a temporary prefix; its libraries
  were selected with `LD_LIBRARY_PATH` for the Clang driver.
- Current upstream master is `8b25adf131b4886dfc11f1229c1acce621646326`
  (including merged PR 2190). Its Make-built ICG sets
  `LangOptions::GNUCVersion` from the host GCC version and suppresses system
  diagnostics. The experimental migration
  in [fork PR #1](https://github.com/brendanny/trick/pull/1) uses Clang's 4.2.1 GNU compatibility value and treats
  system-header errors as failures for every output layout.

## Reproduction without building Trick

On the environment above, with the matching driver available as `clang++-14`:

```sh
printf '#include <cstdlib>\n' > /tmp/icg-system.hh
clang++-14 -std=c++17 -fsyntax-only /tmp/icg-system.hh
clang++-14 -std=c++17 -fgnuc-version=13.3.0 -fsyntax-only /tmp/icg-system.hh
```

Observed: the first command succeeds. The second fails in glibc's `stdlib.h`
with unknown `_Float32`, `_Float64`, and related types, plus
`'__malloc__' attribute takes no arguments`. Advertising the host GCC version
cannot simply replace Clang's compatibility macros.

Using the compatibility macros creates a separate model-layout risk:

```cpp
struct Model {
#if __GNUC__ >= 8
    int gcc_field;
#else
    double clang_field;
#endif
};
```

GCC 13.3 compiles `gcc_field`; default Clang 14 and native ICG see `clang_field`.
Changing ICG output layout does not repair this mismatch. Core-layout parity
compares two invocations of the same native ICG; it does not prove equivalence
to the model compiler.

## Expected resolution

Define and report a supported model/frontend policy that handles compiler-gated
headers explicitly. System-header parse failures must be visible, and metadata
must not silently describe a layout different from the compiled model. Qualify
the policy with GCC-gated model fixtures and the minimum supported LLVM and
platform headers before C1 enables the native route for general simulations.

The migration now prints system-header diagnostics for Make-built ICG when
`--output-root` is requested. A real legacy Makefile build and the native build
run the same regression: the error must appear on stderr, exit must be nonzero,
and any old success stamp/manifest must be removed. This visibility fix does not
resolve the layout-policy issue above and is not yet part of upstream master.
