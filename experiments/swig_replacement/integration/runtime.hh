#pragma once
#include "trick/MemoryManager.hh"
#include <cstddef>
#include <memory>
#include <stdexcept>
#include <string>

namespace binding {
enum class Owner { python, manager };
struct State {
    void* address = nullptr;
    unsigned int id = 0;
    unsigned long generation = 0;
    Owner owner = Owner::manager;
    TRICK_ALLOC_TYPE allocation = TRICK_ALLOC_OTHER;
    void (*destroy)(void*) = nullptr;
    ~State();
    void* checked() const;
    void adopt(const std::string& name);
};

std::shared_ptr<State> make_state(void* address, const char* type, Owner owner,
                                TRICK_ALLOC_TYPE allocation, void (*destroy)(void*));
std::shared_ptr<State> borrow_state(void* address, const char* type);
ALLOC_INFO* named(const std::string& name);
std::string checkpoint();
void restore(const std::string& text);
void erase(const std::string& name);
int allocation_count();
void initialize(const char* core_library, const char* model_library);

template<class T> struct Handle {
    std::shared_ptr<State> state;
    std::ptrdiff_t offset = 0;
    T* get() const {
        return reinterpret_cast<T*>(static_cast<char*>(state->checked()) + offset);
    }
    bool owns() const { return state->owner == Owner::python; }
    void adopt(const std::string& name) const {
        if (offset != 0) throw std::runtime_error("cannot adopt an interior object");
        // Offset zero alone is not sufficient: a first member shares its root's
        // address. The generated bindings check the root type as well.
        state->adopt(name);
    }
    template<class U> Handle<U> child(U* member) const {
        auto root = static_cast<char*>(state->checked());
        return {state, reinterpret_cast<char*>(member) - root};
    }
};
template<class T> Handle<T> borrow(void* address, const char* type) {
    return {borrow_state(address, type), 0};
}
template<class T> void adopt(const Handle<T>& object, const char* type, const std::string& name) {
    object.get();
    auto info = trick_MM->get_alloc_info_at(object.state->address);
    if (!info || !info->user_type_name || type != std::string(info->user_type_name))
        throw std::runtime_error("cannot adopt an interior object or a different root type");
    object.adopt(name);
}
}
