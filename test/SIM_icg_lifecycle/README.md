# ICG MemoryManager lifecycle integration

This simulation uses the production Perl/ICG/SWIG build and the six instrumented
types from `tools/icg_baseline/lifecycle/fixtures`. It is a focused evidence gate
for the ICG rewrite; generated allocation functions and MemoryManager are real.

Run it through `tools/icg_baseline/simulation.py --case memorymanager` with
`--extractor` pointing to a built standalone extractor. The configured CI lane
captures cold/warm/forced/rebuilt output and runs the observations at time 0.1
after both ordinary and forced-generation builds. See
[the runtime contract](../../tools/icg_baseline/runtime/README.md#memorymanager-lifecycle-contract).

The probe checks allocation records, name and interior-address lookup, array
destruction order, removal before destructor callbacks, external unregistration,
and the production SWIG `TMMName` transfer to scalar-new ownership. It never
changes allocation ownership flags itself. The two unavailable-constructor
requests are deliberately anonymous: the current production named-request
failure path leaks its allocated name, an existing issue outside this gate.
