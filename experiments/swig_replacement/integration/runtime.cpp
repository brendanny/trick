#include "runtime.hh"
#include "poc.hh"
#include <dlfcn.h>
#include <map>
#include <regex>
#include <sstream>

namespace binding {
namespace {
unsigned long generation = 0;
std::map<void*, std::weak_ptr<State>> states;
}
void initialize(const char* core_library, const char* model_library) {
    poc_initialize(core_library);
    // add_shared_library_symbols returns zero even on failure at this pin.
    auto handle = dlopen(model_library, RTLD_NOW | RTLD_LOCAL);
    if (!handle) throw std::runtime_error("cannot load generated model metadata");
    trick_MM->add_shared_library_symbols(model_library);
    dlclose(handle);
    trick_MM->set_hexfloat_checkpoint(true);
}
ALLOC_INFO* named(const std::string& name) {
    for (auto it = trick_MM->alloc_info_map_begin(); it != trick_MM->alloc_info_map_end(); ++it)
        if (it->second->name && name == it->second->name) return it->second;
    throw std::runtime_error("unknown allocation: " + name);
}
void* State::checked() const {
    auto info = trick_MM->get_alloc_info_at(address);
    if (!info || info->id != id || (owner == Owner::manager && generation != binding::generation))
        throw std::runtime_error("stale model handle");
    return address;
}
State::~State() {
    if (owner == Owner::python) {
        auto info = trick_MM->get_alloc_info_at(address);
        // Removing an external registration does not free storage. Our explicit
        // allocation recipe then destroys/frees it exactly once.
        if (info && info->id == id) trick_MM->delete_var(address);
        destroy(address);
    }
    auto found = states.find(address);
    if (found != states.end() && found->second.expired()) states.erase(found);
}
void State::adopt(const std::string& name) {
    checked();
    if (owner != Owner::python) throw std::runtime_error("object is already owned by Trick");
    static const std::regex identifier("[A-Za-z_][A-Za-z_0-9]*");
    if (!std::regex_match(name, identifier)) throw std::invalid_argument("allocation name must be an identifier");
    for (auto it = trick_MM->alloc_info_map_begin(); it != trick_MM->alloc_info_map_end(); ++it)
        if (it->second->name && name == it->second->name) throw std::runtime_error("allocation name already exists");
    auto info = trick_MM->get_alloc_info_at(address);
    if (info->name) throw std::runtime_error("cannot rename an already named external allocation");
    if (trick_MM->set_name_at(address, name.c_str())) throw std::runtime_error("naming allocation failed");
    info->stcl = TRICK_LOCAL;
    info->alloc_type = allocation;
    owner = Owner::manager;
    generation = binding::generation;
}
std::shared_ptr<State> make_state(void* address, const char* type, Owner owner,
                                TRICK_ALLOC_TYPE allocation, void (*destroy)(void*)) {
    auto info = trick_MM->get_alloc_info_at(address);
    if (!info) {
        if (!trick_MM->declare_extern_var(address, TRICK_STRUCTURED, type, 0, "", 0, nullptr))
            throw std::runtime_error("cannot register model");
        info = trick_MM->get_alloc_info_at(address);
    }
    auto result = std::make_shared<State>();
    result->address = address; result->id = info->id; result->generation = generation;
    result->allocation = allocation; result->destroy = destroy;
    states[address] = result;
    // The constructor's guard retains ownership until every allocation in this
    // function succeeds, including insertion in the weak registry.
    result->owner = owner;
    return result;
}
std::shared_ptr<State> borrow_state(void* address, const char* type) {
    auto info = trick_MM->get_alloc_info_at(address);
    if (!info || !info->user_type_name || type != std::string(info->user_type_name))
        throw std::runtime_error("cast requires a registered allocation of the requested type");
    auto found = states.find(address);
    if (found != states.end()) {
        if (auto state = found->second.lock()) {
            if (state->id == info->id && (state->owner == Owner::python || state->generation == generation)) return state;
        }
    }
    return make_state(address, type, Owner::manager, info->alloc_type, nullptr);
}
std::string checkpoint() {
    std::ostringstream out; trick_MM->write_checkpoint(out); return out.str();
}
void restore(const std::string& text) {
    ++generation;
    std::istringstream in(text);
    // The return value alone is insufficient at this pin. The public state
    // getter preserves error reporting AND the normal STL restore path.
    trick_MM->set_checkpoint_restore_state(false);
    trick_MM->init_from_checkpoint(&in, true);
    if (!trick_MM->get_checkpoint_restore_state()) throw std::runtime_error("checkpoint restore failed");
}
void erase(const std::string& name) {
    auto info = named(name);
    if (info->stcl != TRICK_LOCAL) throw std::runtime_error("erase requires manager-owned storage");
    if (trick_MM->delete_var(name)) throw std::runtime_error("erase failed");
}
int allocation_count() {
    return std::distance(trick_MM->alloc_info_map_begin(), trick_MM->alloc_info_map_end());
}
}
