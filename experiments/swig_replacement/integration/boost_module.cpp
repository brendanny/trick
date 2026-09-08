#include "boost_bindings.hh"
#include "models.hh"
#include <boost/version.hpp>

namespace bp = boost::python;
double integration_stop_time = 2.0;
const char* integration_binding_backend = "boost";
std::string integration_binding_version = std::to_string(BOOST_VERSION / 100000) + "." +
    std::to_string(BOOST_VERSION / 100 % 1000) + "." + std::to_string(BOOST_VERSION % 100);

BOOST_PYTHON_MODULE(trick) {
    using namespace binding;
    // More-specific translators are registered last and tried first.
    bp::register_exception_translator<std::exception>(+[](const std::exception& e) { PyErr_SetString(PyExc_RuntimeError, e.what()); });
    bp::register_exception_translator<std::invalid_argument>(+[](const std::invalid_argument& e) { PyErr_SetString(PyExc_ValueError, e.what()); });
    bp::register_exception_translator<std::out_of_range>(+[](const std::out_of_range& e) { PyErr_SetString(PyExc_IndexError, e.what()); });
    bp::class_<Quantity>("Quantity", bp::no_init);
    bp::def("attach_units", +[](const std::string& units, double value) { return Quantity{units, value}; });
    bp::class_<DoubleView>("DoubleView", bp::no_init)
        .def("__len__", &DoubleView::size)
        .def("__getitem__", &DoubleView::get)
        .def("__setitem__", &set_item)
        .def("append", &append_value)
        .def("assign", &assign_values);
    bp::def("checkpoint", &checkpoint);
    bp::def("restore", &restore);
    bp::def("erase", &erase);
    bp::def("allocation_count", &allocation_count);
    bp::def("probe_constructions", &probe_constructions);
    bp::def("probe_destructions", &probe_destructions);
    bp::def("stop", +[](double time) {
        if (time <= 0 || time > 10) throw std::invalid_argument("headless experiment accepts stop time in (0, 10]");
        integration_stop_time = time;
    });
    bind_generated_boost();
    bp::scope().attr("sim_services") = bp::scope();
}
// Keep IPPython unchanged, including its real Py_Finalize shutdown path.
extern "C" void init_swig_modules() {
    if (PyImport_AppendInittab("trick", &PyInit_trick) < 0)
        throw std::runtime_error("cannot register Boost.Python module");
}
