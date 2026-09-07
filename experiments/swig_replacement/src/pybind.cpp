#include <pybind11/pybind11.h>
#include <pybind11/stl_bind.h>
#include "poc.hh"
PYBIND11_MAKE_OPAQUE(std::vector<double>);
namespace b = pybind11;
PYBIND11_MODULE(poc_pybind, m) {
    b::class_<POCLeft>(m, "Left"); b::class_<POCRight>(m, "Right");
    b::bind_vector<std::vector<double>>(m, "DoubleVector");
    b::class_<POCModel, POCLeft, POCRight>(m, "Model")
        .def(b::init<double>()).def_readwrite("mass", &POCModel::mass)
        .def_readwrite("samples", &POCModel::samples)
        .def("adjust", b::overload_cast<int>(&POCModel::adjust))
        .def("adjust", b::overload_cast<double>(&POCModel::adjust))
        .def("position_get", &POCModel::position_get).def("position_set", &POCModel::position_set)
        .def("sample_push", &POCModel::sample_push).def("sample_get", &POCModel::sample_get);
    b::class_<POCAllocated>(m, "Allocated")
        .def(b::init<double>()).def("registered", &POCAllocated::registered);
    m.def("new_allocated", &poc_new_allocated, b::return_value_policy::take_ownership);
    #include "common_bindings.inc"
}
