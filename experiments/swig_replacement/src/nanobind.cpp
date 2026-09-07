#include <nanobind/nanobind.h>
#include <nanobind/stl/bind_vector.h>
#include <nanobind/stl/shared_ptr.h>
#include "poc.hh"
NB_MAKE_OPAQUE(std::vector<double>);
namespace b = nanobind;
static std::shared_ptr<POCAllocated> owned_allocated(double value) {
    // A shared_ptr owner preserves the class-specific delete expression. Raw
    // take_ownership invokes destruction/global deallocation and leaves Trick's
    // registration behind; negative_cases.py preserves that observation.
    return std::shared_ptr<POCAllocated>(poc_new_allocated(value));
}
NB_MODULE(poc_nanobind, m) {
    b::class_<POCLeft>(m, "Left"); b::class_<POCRight>(m, "Right");
    b::bind_vector<std::vector<double>>(m, "DoubleVector");
    // Nanobind registers a single C++ base. The second-base conversion test
    // intentionally records that limitation instead of hiding it in a lambda.
    b::class_<POCModel, POCLeft>(m, "Model")
        .def(b::init<double>()).def_rw("mass", &POCModel::mass)
        .def_rw("samples", &POCModel::samples)
        .def("adjust", b::overload_cast<int>(&POCModel::adjust))
        .def("adjust", b::overload_cast<double>(&POCModel::adjust))
        .def("position_get", &POCModel::position_get).def("position_set", &POCModel::position_set)
        .def("sample_push", &POCModel::sample_push).def("sample_get", &POCModel::sample_get);
    b::class_<POCAllocated>(m, "Allocated")
        .def(b::new_(&owned_allocated)).def("registered", &POCAllocated::registered);
    m.def("new_allocated", &owned_allocated);
    m.def("raw_new_allocated", &poc_new_allocated, b::rv_policy::take_ownership);
    #include "common_bindings.inc"
}
