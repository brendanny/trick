#pragma once
#include "values.hh"
#include "poc.hh"
#include <pybind11/pybind11.h>
#include <vector>

namespace binding {
namespace py = pybind11;
inline double number(py::handle value, const char* units) {
    if (py::isinstance<Quantity>(value)) {
        auto q = py::cast<Quantity>(value);
        return poc_convert(q.value, q.units.c_str(), units);
    }
    return py::cast<double>(value);
}
inline void set_item(const DoubleView& view, std::ptrdiff_t i, py::handle value) {
    view.set(i, number(value, view.units.c_str()));
}
inline void assign_values(const DoubleView& view, py::iterable values) {
    std::vector<double> converted;
    for (auto value : values) converted.push_back(number(value, view.units.c_str()));
    view.assign(std::move(converted));
}
inline void append_value(const DoubleView& view, py::handle value) {
    if (view.count) throw py::type_error("cannot append to a fixed array");
    view.append(number(value, view.units.c_str()));
}
template<class T, class... Args> Handle<T> construct(const char* type, TRICK_ALLOC_TYPE allocation,
                                                  void (*destroy)(void*), py::object name, Args... args) {
    auto handle = construct_native<T>(type, allocation, destroy, args...);
    if (!name.is_none()) adopt(handle, type, name.cast<std::string>());
    return handle;
}
void bind_runtime(py::module_& m);
void bind_generated(py::module_& m);
}
