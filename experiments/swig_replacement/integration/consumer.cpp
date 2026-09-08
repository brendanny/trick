#include "bindings.hh"
#include "models.hh"
PYBIND11_MODULE(_msd_consumer, m) {
    m.def("mass", [](const binding::Handle<MSD>& object) { return object.get()->m; });
    m.def("echo", [](const binding::Handle<MSD>& object) { object.get(); return object; });
}
