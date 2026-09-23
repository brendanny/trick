# B3: selectable integrators

Predecessor: B2. `TRICK_BUILD_INTEGRATORS=ON` enables MemoryManager and exposes
`Trick::Integrators`. `TRICK_USE_ER7_UTILS=ON` (default) links the bundled
`Trick::Er7Utils`; `OFF` selects the existing Trick algorithm sources. Both use
explicit source inventories. Integration schedulers remain B5 Core sources.

The choice propagates `USE_ER7_UTILS_INTEGRATORS` to consumers; `TRICK_VER` and
`TRICK_MINOR` are also public so inline allocations and layouts agree with the
library. ER7 uses the real Trick memory manager, including primitive allocation.

The bundled source has no CheckpointHelper. Requesting
`TRICK_USE_ER7_CHECKPOINTHELPER=ON` fails explicitly. An external ER7/CheckpointHelper
variant is not silently discovered; it needs its own reviewed dependency and
source contract before qualification.

Acceptance: build and run `ctest --test-dir <build> -L integrators
--output-on-failure` in separate ON and OFF configurations. The smoke integrates
one state with a constant derivative and checks the analytic result. With ER7 it
uses the concrete Euler implementation; with ER7 off it uses Trick's Euler
integrator. Both use production libraries and MemoryManager; standalone tests
supply only message and fatal-diagnostic boundaries. Full factory allocation and
scheduler integration require B4/B5 registration and are validated later.

BD-18: native targets propagate implementation and allocator requirements.
There is one owner for each algorithm source; no recursive Make or object glob.
