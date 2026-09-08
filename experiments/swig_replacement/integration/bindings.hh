#pragma once
#include "runtime.hh"
#include "poc.hh"
#include <pybind11/pybind11.h>
#include <vector>

namespace binding {
namespace py = pybind11;
struct Quantity { std::string units; double value; };
inline double number(py::handle value, const char* units) {
    if (py::isinstance<Quantity>(value)) {
        auto q = py::cast<Quantity>(value);
        return poc_convert(q.value, q.units.c_str(), units);
    }
    return py::cast<double>(value);
}
struct DoubleView {
    std::shared_ptr<State> state;
    std::ptrdiff_t offset;
    std::size_t count; // zero marks a vector
    std::string units;
    void* address() const { return static_cast<char*>(state->checked()) + offset; }
    std::size_t size() const { return count ? (address(), count) : static_cast<std::vector<double>*>(address())->size(); }
    double* data() const { return count ? static_cast<double*>(address()) : static_cast<std::vector<double>*>(address())->data(); }
    std::size_t index(py::ssize_t i) const {
        auto n = static_cast<py::ssize_t>(size());
        if (i < 0) i += n;
        if (i < 0 || i >= n) throw py::index_error("array index out of range");
        return static_cast<std::size_t>(i);
    }
    double get(py::ssize_t i) const { auto at = index(i); return data()[at]; }
    void set(py::ssize_t i, py::handle value) const {
        // Python conversion can call back into the model and resize/delete it.
        auto converted = number(value, units.c_str()); auto at = index(i); data()[at] = converted;
    }
    void assign(py::iterable values) const {
        std::vector<double> converted;
        for (auto value : values) converted.push_back(number(value, units.c_str()));
        if (count) {
            if (converted.size() != size()) throw py::value_error("fixed array length mismatch");
            std::copy(converted.begin(), converted.end(), data());
        } else *static_cast<std::vector<double>*>(address()) = std::move(converted);
    }
    void append(py::handle value) const {
        if (count) throw py::type_error("cannot append to a fixed array");
        auto converted = number(value, units.c_str());
        static_cast<std::vector<double>*>(address())->push_back(converted);
    }
};
template<class T> DoubleView view(const Handle<T>& object, void* member, std::size_t count, const char* units) {
    return {object.state, static_cast<char*>(member) - static_cast<char*>(object.state->checked()), count, units};
}
template<class T, class... Args> Handle<T> construct(const char* type, TRICK_ALLOC_TYPE allocation,
                                                  void (*destroy)(void*), py::object name, Args... args) {
    T* p = new T(args...);
    std::shared_ptr<State> state;
    try { state = make_state(p, type, Owner::python, allocation, destroy); }
    catch (...) {
        if (trick_MM->get_alloc_info_at(p)) trick_MM->delete_var(p);
        destroy(p); throw;
    }
    Handle<T> handle{state, 0};
    if (!name.is_none()) adopt(handle, type, name.cast<std::string>());
    return handle;
}
void bind_runtime(py::module_& m);
void bind_generated(py::module_& m);
}
