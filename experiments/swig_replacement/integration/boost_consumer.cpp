#include "boost_bindings.hh"
#include "models.hh"
BOOST_PYTHON_MODULE(_msd_consumer) {
    boost::python::def("mass", +[](const binding::Handle<MSD>& object) { return object.get()->m; });
    boost::python::def("echo", +[](const binding::Handle<MSD>& object) { object.get(); return object; });
}
