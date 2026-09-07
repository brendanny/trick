#include "poc.hh"
#include "poc_abi.h"
#include <exception>
#include <stdexcept>
namespace { thread_local std::string error; }
extern "C" const char* poc_error() { return error.c_str(); }
extern "C" void* poc_create(int kind, const char* name, double value) {
    error.clear(); try {
        if (kind == 0) return new POCModel(value);
        if (kind == 1) return new POCAllocated(value);
        if (kind == 2) return new POCView(name);
        throw std::invalid_argument("invalid handle kind");
    } catch (const std::exception& e) { error = e.what(); return nullptr; }
}
extern "C" void poc_destroy(int kind, void* handle) {
    error.clear(); try {
        if (kind == 0) delete static_cast<POCModel*>(handle);
        else if (kind == 1) delete static_cast<POCAllocated*>(handle);
        else if (kind == 2) delete static_cast<POCView*>(handle);
        else throw std::invalid_argument("invalid handle kind");
    } catch (const std::exception& e) { error = e.what(); }
}
extern "C" double poc_call(int op, void* h, const char* text, const char* second, int index, double value) {
    error.clear(); try {
        auto m = static_cast<POCModel*>(h); auto v = static_cast<POCView*>(h);
        switch (op) {
        case 0: poc_initialize(text); break;
        case 1: poc_array(text, index); break;
        case 2: poc_managed(text, value); break;
        case 3: poc_resize(text, index); break;
        case 4: poc_erase(text); break;
        case 5: poc_restore(text); break;
        case 6: return poc_convert(value, text, second);
        case 7: return poc_live_models();
        case 8: return poc_live_allocated();
        case 9: return poc_allocations();
        case 10: return m->mass;
        case 11: m->mass = value; break;
        case 12: return m->adjust(index);
        case 13: return m->adjust(value);
        case 14: return m->position_get(index);
        case 15: m->position_set(index, value); break;
        case 16: m->sample_push(value); break;
        case 17: return m->sample_get(index);
        case 18: return static_cast<POCAllocated*>(h)->registered();
        case 19: return poc_left(m);
        case 20: return poc_right(m);
        case 21: return poc_right_offset(m);
        case 22: return v->get(index);
        case 23: v->set(index, value); break;
        case 24: return v->size();
        case 25: return v->field_get(text);
        case 26: v->field_set(text, value); break;
        case 27: return v->call_adjust(value);
        default: throw std::invalid_argument("invalid operation");
        }
        return 0;
    } catch (const std::exception& e) { error = e.what(); return 0; }
}
extern "C" const char* poc_text() {
    error.clear(); try { return poc_checkpoint(); }
    catch (const std::exception& e) { error = e.what(); return nullptr; }
}
