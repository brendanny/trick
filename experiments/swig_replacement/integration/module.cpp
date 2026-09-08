#include "bindings.hh"
#include "models.hh"
namespace py = pybind11;
double integration_stop_time = 2.0;
const char* integration_binding_backend = "pybind";
std::string integration_binding_version = std::to_string(PYBIND11_VERSION_MAJOR) + "." +
    std::to_string(PYBIND11_VERSION_MINOR) + "." + std::to_string(PYBIND11_VERSION_PATCH);
namespace binding {
void bind_runtime(py::module_& m) {
    py::class_<Quantity>(m, "Quantity");
    m.def("attach_units", [](const std::string& units, double value) { return Quantity{units, value}; });
    py::class_<DoubleView>(m, "DoubleView")
        .def("__len__", &DoubleView::size)
        .def("__getitem__", &DoubleView::get)
        .def("__setitem__", &set_item)
        .def("append", &append_value)
        .def("assign", &assign_values);
    m.def("checkpoint", &checkpoint);
    m.def("restore", &restore);
    m.def("erase", &erase);
    m.def("allocation_count", &allocation_count);
    m.def("probe_constructions", &probe_constructions);
    m.def("probe_destructions", &probe_destructions);
    m.def("stop", [](double time) {
        if (time <= 0 || time > 10) throw py::value_error("headless experiment accepts stop time in (0, 10]");
        integration_stop_time = time;
    });
}
}
PYBIND11_MODULE(trick, m) {
    binding::bind_runtime(m);
    binding::bind_generated(m);
    m.attr("sim_services") = m;
}
// Actual IPPython calls this legacy-named hook before Py_Initialize. Its
// implementation registers a pybind11 module; no SWIG runtime is linked.
extern "C" void init_swig_modules() {
    if (PyImport_AppendInittab("trick", &PyInit_trick) < 0)
        throw std::runtime_error("cannot register pybind11 module");
}
