#pragma once
#include "values.hh"
#include "poc.hh"
#include <boost/python.hpp>
#include <boost/python/stl_iterator.hpp>

namespace binding {
namespace bp = boost::python;
inline double number(const bp::object& value, const char* units) {
    bp::extract<Quantity> quantity(value);
    if (quantity.check()) {
        auto q = quantity();
        return poc_convert(q.value, q.units.c_str(), units);
    }
    // Match Python numeric conversion, including user-defined __float__.
    double result = PyFloat_AsDouble(value.ptr());
    if (PyErr_Occurred()) bp::throw_error_already_set();
    return result;
}
inline void set_item(const DoubleView& view, std::ptrdiff_t i, bp::object value) {
    view.set(i, number(value, view.units.c_str()));
}
inline void assign_values(const DoubleView& view, bp::object values) {
    std::vector<double> converted;
    bp::stl_input_iterator<bp::object> next(values), end;
    for (; next != end; ++next) converted.push_back(number(*next, view.units.c_str()));
    view.assign(std::move(converted));
}
inline void append_value(const DoubleView& view, bp::object value) {
    if (view.count) {
        PyErr_SetString(PyExc_TypeError, "cannot append to a fixed array");
        bp::throw_error_already_set();
    }
    view.append(number(value, view.units.c_str()));
}
template<class T, class... Args> Handle<T>* construct_boost(
    const char* type, TRICK_ALLOC_TYPE allocation, void (*destroy)(void*), bp::object name, Args... args) {
    auto handle = construct_native<T>(type, allocation, destroy, args...);
    if (!name.is_none()) adopt(handle, type, bp::extract<std::string>(name)());
    // Boost owns only the checked handle. State decides who owns native storage.
    return new Handle<T>(std::move(handle));
}
void bind_generated_boost();
}
