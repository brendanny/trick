# SWIG replacement feasibility experiments

Eight runnable implementations cover the seven options from the investigation:
pybind11, nanobind, reflection plus callable wrappers, direct CPython, Shiboken6,
cppyy/Cling, and **both Cython and CFFI** for the seventh option.

The base is NASA Trick commit
[`c5ba06ea79a8a9ecc3fa4938fd45a77b1e7b9e43`](https://github.com/nasa/trick/commit/c5ba06ea79a8a9ecc3fa4938fd45a77b1e7b9e43).
Everything added lives in this directory. Its standalone build invokes no SWIG
and compiles no SWIG-generated wrappers. The normal Trick build and its SWIG
dependencies remain in place.

**Result:** all eight implementations pass their implemented checks in both a
Python process and a C++ executable embedding Python. This establishes a useful
prototype boundary, not complete replacement feasibility. **Generated pybind11
plus a shared Trick runtime remains the first candidate to advance.** Nanobind
requires significant compatibility adaptations; Shiboken and cppyy merit further
generation/deployment experiments. Reflection is a credible shared data layer.
CPython, Cython and CFFI demonstrate explicit runtime/ABI alternatives.

See [the measured results and per-option implications](results/RESULTS.md) and
[the complete machine-readable run](results/linux-gcc13-python312.json).

The [follow-on pybind11 integration experiment](integration/README.md) now adds
generated declarations/metadata/bindings, Python-to-MM ownership transfer, the
actual `IPPython` lifecycle, and MSD integration with STL checkpoint/restart.
The eight-backend comparison and its boundaries below remain the first-stage
record; the follow-on has its own narrower coverage and results.

## Reproduce

Tested on Linux x86_64, GCC 13.3, Python 3.12.13, Flex 2.6.4, Bison 3.8.2 and
UDUNITS 2.2.28. This is currently a Linux build: its shared-library handling,
linker flags and dependency discovery have not been ported to macOS/Windows.
The exact Python dependencies are in [requirements.txt](requirements.txt).

On an Ubuntu 24.04 development machine, install the native prerequisites and run
from this directory:

```bash
sudo apt-get install build-essential python3-dev python3-venv flex bison libudunits2-dev
python3 -m venv venv
. venv/bin/activate
CC=gcc CXX=g++ python -m pip install -r requirements.txt
python build.py --jobs 4
python run.py
```

cppyy's Python extension may build from source during installation. All eight
dependencies are installed for this comparison; they are not proposed as eight
simultaneous production dependencies.

`build.py` builds the real Trick subset, five compiled adapters, an embedding
executable, and Shiboken-generated bindings. It separately compiles an expected
nanobind incompatibility probe. A recognized incompatibility is recorded as
`observed_limitation`; an unrelated build error remains a failure. Build logs and
`build-results.json` are retained under `build/`.

`run.py` uses a fresh subprocess for each backend and mode. It saves `results.json`
and full logs under `build/`, continues past individual process failures, and
returns nonzero for unexpected failures. `pass` means the implemented checks
succeeded; **`limitation` is never counted as a passing check**. Some limitations
are observed library behavior, while others identify work this adapter has not
implemented. Read the case detail rather than ranking by pass count.

Useful variations:

```bash
python run.py --backends pybind nanobind --modes import
python build.py --build-dir build/fresh --jobs 4
python run.py --build-dir build/fresh --output build/fresh/results.json
```

For native dependencies installed under a separate prefix, pass
`build.py --native-prefix /path/to/prefix`. It expects `include`, `lib`, `bin` and
`share` beneath that prefix; `run.py` discovers the UDUNITS XML there. You can also
set `UDUNITS2_XML_PATH` explicitly. This is how the recorded run used extracted
Ubuntu packages without a system installation.

Shiboken needs Clang builtin headers in addition to its generator wheel. The
script accepts `--clang-include /path/to/clang/include` and otherwise uses the
headers shipped with the installed cppyy toolchain. The recorded run used those
Clang 16 headers with Shiboken's bundled Clang 20 parser. Shiboken emitted a
builtin-directory discovery warning; parsing, compilation and execution all
succeeded with the explicit include path. A production toolchain should pin a
matched parser/header installation.

## What is exercised

The shared library builds **the repository's actual MemoryManager sources,
Flex/Bison declaration and reference parsers, ClassicCheckPointAgent,
UDUNITS integration, and linked-list utility**. The only replaced simulation
service is `message_publish`, a stderr logging shim. `TRICK_VER` selects the
normal shared UDUNITS implementation. There is no fake memory manager or fake
checkpoint serializer.

| Component | Role |
|---|---|
| [poc.hh](include/poc.hh), [fixture.cpp](src/fixture.cpp) | Model with two C++ bases, overloads, fixed array and vector; a separate class with the real `TRICK_MM_INTERFACE`; checked MM views; units and checkpoint operations |
| [pybind.cpp](src/pybind.cpp), [nanobind.cpp](src/nanobind.cpp) | Representative template-library bindings, explicit vector views and ownership policies |
| [poc_reflection.py](python/poc_reflection.py) | Generic Python attribute syntax over real Trick `ATTRIBUTES`, plus a selected typed callable thunk |
| [cpython.cpp](src/cpython.cpp) | Manual Python types, reference counts, properties, dispatch and exception translation |
| [typesystem.xml](shiboken/typesystem.xml) | Actual Shiboken generation, ownership and exception rules |
| [adapters.py](python/adapters.py) | Name normalization, cppyy runtime header parsing/library loading and ownership policy |
| [poc_cython.pyx](python/poc_cython.pyx) | Cython C++ declarations, extension classes and explicit destruction |
| [poc_abi.h](include/poc_abi.h), [abi.cpp](src/abi.cpp), [poc_cffi.py](python/poc_cffi.py) | C ABI with exception containment, owned opaque handles and CFFI ABI-mode facade |
| [cases.py](python/cases.py), [embed.cpp](src/embed.cpp) | Common behavioral checks, including execution on a native worker thread with GIL acquisition and interpreter finalization |

The core checks cover:

* Native construction, scalar mutation, distinguishable int/double overloads,
  fixed-array and vector operations, exception translation and destruction.
* C++ base-pointer conversion through a nonzero secondary-base offset, separately
  from Python `isinstance` recognition of both bases.
* Real custom allocation registration and removal for Python-owned objects,
  including explicitly owned factory results.
* Borrowed array aliases that share live MM storage, enforce bounds, and do not
  delete simulation storage when a Python wrapper is collected.
* Actual MM resize and deletion, rejection of stale views, and allocation-name
  reuse without accidentally reconnecting an old view to a new allocation.
* Actual checkpoint serialization/restoration of a C++ record and a double
  array; invalid checkpoint input; invalidation of old Python handles.
* UDUNITS scale conversion, affine temperature conversion and incompatible units.
* Native live vector properties and parent retention where implemented.
* Generic reflected scalar properties and selected callable dispatch.

The embedding executable initializes Python using `PyConfig`, runs the cases on
a C++ worker thread using `PyGILState_Ensure`, joins it, and calls `Py_FinalizeEx`.
It does **not** exercise parallel model access, multiple interpreters, interpreter
restart, a free-threaded Python build, or the actual Trick scheduler.

## Boundaries that matter

**The common runtime supplies invalidation.** `POCView` stores a name, allocation
ID and epoch, then resolves the allocation on every operation. Resize and restore
through this fixture increment the epoch. This conservatively invalidates every
existing view. A production design must put notifications in the MM lifecycle
itself, synchronize access, and handle changes made outside these fixture entry
points. None of these libraries automatically made arbitrary borrowed C++
pointers safe. Raw native classes are tested separately from managed views.

**The reflection prototype is a hybrid, not an eighth binding library.** It reuses
the manual CPython checked-handle runtime. Data fields are discovered through
Trick's real attribute table; only scalar doubles are supported. `call_adjust`
is one hand-authored representative typed thunk. It does not derive callable
signatures from `ATTRIBUTES`, which contain data metadata.

**ICG output is represented, not regenerated.** Attribute tables and the model's
`io_src_*` hooks are hand-authored equivalents for this fixture. Most bindings
are also hand-authored. Shiboken generates actual wrappers, Cython generates C++
from the supplied declarations, and cppyy parses the header at runtime. There
is no general replacement generator for arbitrary Trick model headers yet.
Shiboken's parser sees `POC_GENERATOR`, which hides allocation declarations only;
its generated C++ includes the real allocation macro. Class layouts are the same.

**Checkpoint coverage is intentionally bounded.** At this pin, both
`MemoryManager::init_from_checkpoint` and `read_checkpoint` discard the checkpoint
agent's error status. The fixture resets MM and directly invokes its real
checkpoint agent so parse errors can cross the Python boundary. It does not
exercise the omitted STL/anonymous-allocation postprocessing, scheduler hooks,
or a production checkpoint restart. The vector test is separate from checkpoint
serialization: the fixture's vector is absent from its checkpoint attributes.

**Ownership transfer remains unproven.** The tests distinguish Python ownership,
factory ownership and MM ownership, but do not transfer an existing Python-owned
object into MM using `TMMName`-equivalent semantics. That requires per-backend
disown/adoption logic and safe handling of all outstanding aliases. The custom
allocator class is tested under Python ownership; the checkpointed model is a
separate class allocated by MM. Do not read the combination as proof of every
custom-allocator/checkpoint ownership interaction.

Other unimplemented coverage includes Python virtual overrides/directors,
callbacks retaining Python objects, nested pointer graphs, multidimensional
array slicing, enums/bitfields/unions, full STL persistence, units-bearing value
objects and assignment typemaps, `thisown`/`__swig_*` script compatibility,
cross-module type identity, and real `trickify` and `S_define` builds. The existing
Trick simulation suites, sanitizers and compiler/OS matrix have not been run.

## Next experiment before selecting a replacement

Generate bindings for an existing simulation from a shared declaration model,
then run its unmodified input script through the actual `IPPython` lifecycle.
Include `TMMName` ownership transfer, custom-allocated model checkpoint/restart,
STL aliases, unit-aware assignments and a separately loaded model library.

The main integration points remain
[`bin/trick-CP`](../../bin/trick-CP),
[`Interface_Code_Gen`](../../trick_source/codegen/Interface_Code_Gen),
[`trick_swig`](../../trick_source/trick_swig),
[`IPPython.cpp`](../../trick_source/sim_services/InputProcessor/IPPython.cpp),
and the configuration/makefile dependency graph. This experiment provides
executable evidence for that work; it does not remove those integration points.
