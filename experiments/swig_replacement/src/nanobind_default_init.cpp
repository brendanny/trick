// Intentionally compiled separately: nb::init's void* placement new conflicts
// with TRICK_MM_INTERFACE's class-specific allocation overloads at the pin.
#include <nanobind/nanobind.h>
#include "poc.hh"
NB_MODULE(poc_nanobind_default_init, m) {
    nanobind::class_<POCAllocated>(m, "Allocated").def(nanobind::init<double>());
}
