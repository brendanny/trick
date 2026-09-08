#pragma once
#include "runtime.hh"
#include <algorithm>
#include <vector>

namespace binding {
struct Quantity { std::string units; double value; };
// Conversion from Python finishes before any mutating operation below. A
// conversion can invoke Python code which resizes, deletes or restores a model.
struct DoubleView {
    std::shared_ptr<State> state;
    std::ptrdiff_t offset;
    std::size_t count; // zero marks a vector
    std::string units;
    void* address() const { return static_cast<char*>(state->checked()) + offset; }
    std::size_t size() const { return count ? (address(), count) : static_cast<std::vector<double>*>(address())->size(); }
    double* data() const { return count ? static_cast<double*>(address()) : static_cast<std::vector<double>*>(address())->data(); }
    std::size_t index(std::ptrdiff_t i) const {
        auto n = static_cast<std::ptrdiff_t>(size());
        if (i < 0) i += n;
        if (i < 0 || i >= n) throw std::out_of_range("array index out of range");
        return static_cast<std::size_t>(i);
    }
    double get(std::ptrdiff_t i) const { auto at = index(i); return data()[at]; }
    void set(std::ptrdiff_t i, double value) const { auto at = index(i); data()[at] = value; }
    void assign(std::vector<double> converted) const {
        if (count) {
            if (converted.size() != size()) throw std::invalid_argument("fixed array length mismatch");
            std::copy(converted.begin(), converted.end(), data());
        } else *static_cast<std::vector<double>*>(address()) = std::move(converted);
    }
    void append(double value) const {
        if (count) throw std::invalid_argument("cannot append to a fixed array");
        static_cast<std::vector<double>*>(address())->push_back(value);
    }
};
template<class T> DoubleView view(const Handle<T>& object, void* member, std::size_t count, const char* units) {
    return {object.state, static_cast<char*>(member) - static_cast<char*>(object.state->checked()), count, units};
}
}
