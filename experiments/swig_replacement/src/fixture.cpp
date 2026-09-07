#include "poc.hh"
#include "trick/UdUnits.hh"
#include <udunits2.h>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <sstream>
#include <stdexcept>

namespace {
int models = 0, allocated = 0;
unsigned long epoch = 0;
ALLOC_INFO* find(const std::string& name) {
    if (!trick_MM) throw std::runtime_error("initialize first");
    for (auto it = trick_MM->alloc_info_map_begin(); it != trick_MM->alloc_info_map_end(); ++it)
        if (it->second->name && name == it->second->name) return it->second;
    throw std::runtime_error("allocation no longer exists: " + name);
}
void index_check(int index, int count) {
    if (index < 0 || index >= count) throw std::out_of_range("index out of range");
}
}

// Only the message service is replaced in this standalone subset. All memory,
// attribute parsing, checkpoint serialization/restoration and units code is real.
extern "C" int message_publish(int, const char* format, ...) {
    va_list args; va_start(args, format);
    int result = vfprintf(stderr, format, args); va_end(args); return result;
}

POCModel::POCModel(double value) : mass(value) { ++models; }
POCModel::~POCModel() { --models; }
double POCModel::adjust(int value) { return mass += value * 2; }
double POCModel::adjust(double value) { return mass += value; }
double POCModel::position_get(int index) const { index_check(index, 3); return position[index]; }
void POCModel::position_set(int index, double value) { index_check(index, 3); position[index] = value; }
void POCModel::sample_push(double value) { samples.push_back(value); }
double POCModel::sample_get(int index) const { index_check(index, samples.size()); return samples[index]; }
POCAllocated::POCAllocated(double v) : value(v) { ++allocated; }
POCAllocated::~POCAllocated() { --allocated; }
bool POCAllocated::registered() const { return trick_MM->get_alloc_info_at(const_cast<POCAllocated*>(this)); }
POCAllocated* poc_new_allocated(double value) { return new POCAllocated(value); }
int poc_live_models() { return models; }
int poc_live_allocated() { return allocated; }
int poc_allocations() { return std::distance(trick_MM->alloc_info_map_begin(), trick_MM->alloc_info_map_end()); }
int poc_left(POCLeft* value) { return value->left; }
int poc_right(POCRight* value) { return value->right; }
long poc_right_offset(POCModel* value) { return reinterpret_cast<char*>(static_cast<POCRight*>(value)) - reinterpret_cast<char*>(value); }

// Representative ICG output, hand authored for two fixture classes. This does
// NOT prove a replacement declaration/callable generator for arbitrary headers.
extern "C" {
ATTRIBUTES attrPOCModel[3] = {};
ATTRIBUTES attrPOCAllocated[2] = {};
void init_attrPOCModel_c_intf() {
    static bool initialized = false; if (initialized) return; initialized = true;
    POCModel sample;
    for (int i = 0; i < 2; ++i) {
        auto& a = attrPOCModel[i]; a.type_name = "double"; a.units = i ? "m" : "kg";
        a.io = 15; a.type = TRICK_DOUBLE; a.size = sizeof(double); a.language = Language_CPP;
    }
    attrPOCModel[0].name = "mass";
    attrPOCModel[0].offset = reinterpret_cast<char*>(&sample.mass) - reinterpret_cast<char*>(&sample);
    attrPOCModel[1].name = "position";
    attrPOCModel[1].offset = reinterpret_cast<char*>(sample.position) - reinterpret_cast<char*>(&sample);
    attrPOCModel[1].num_index = 1; attrPOCModel[1].index[0].size = 3;
    attrPOCModel[2].name = "";
}
void init_attrPOCAllocated_c_intf() {
    auto& a = attrPOCAllocated[0]; a.name = "value"; a.type_name = "double"; a.units = "--";
    a.io = 15; a.type = TRICK_DOUBLE; a.size = sizeof(double); a.language = Language_CPP;
    a.offset = 0; attrPOCAllocated[1].name = "";
}
size_t io_src_sizeof_POCModel() { return sizeof(POCModel); }
size_t io_src_sizeof_POCAllocated() { return sizeof(POCAllocated); }
void* io_src_allocate_POCModel(int count) {
    auto p = static_cast<POCModel*>(calloc(count, sizeof(POCModel)));
    if (!p) throw std::bad_alloc();
    for (int i = 0; i < count; ++i) new (&p[i]) POCModel();
    return p;
}
void io_src_destruct_POCModel(void* p, int count) { for (int i = 0; i < count; ++i) static_cast<POCModel*>(p)[i].~POCModel(); }
void io_src_delete_POCModel(void* p) { delete static_cast<POCModel*>(p); }
}

void poc_initialize(const char* library) {
    // One interpreter/manager per process, as in these isolated feasibility runs.
    static Trick::MemoryManager manager;
    static bool initialized = false;
    if (!initialized) {
        manager.add_shared_library_symbols(library);
        static Trick::UdUnits units;
        if (units.read_default_xml()) throw std::runtime_error("UDUNITS XML unavailable");
        initialized = true;
    }
}
void poc_array(const char* name, int count) {
    if (count <= 0) throw std::invalid_argument("positive size required");
    std::string declaration = "double " + std::string(name) + "[" + std::to_string(count) + "]";
    if (!trick_MM->declare_var(declaration.c_str())) throw std::runtime_error("array declaration failed");
}
void poc_managed(const char* name, double value) {
    std::string declaration = "POCModel " + std::string(name);
    auto p = static_cast<POCModel*>(trick_MM->declare_var(declaration.c_str()));
    if (!p) throw std::runtime_error("model declaration failed");
    p->mass = value;
}
void poc_resize(const char* name, int count) {
    if (count <= 0) throw std::invalid_argument("positive size required");
    if (!trick_MM->resize_array(name, count)) throw std::runtime_error("resize failed");
    ++epoch;
}
void poc_erase(const char* name) { if (trick_MM->delete_var(std::string(name))) throw std::runtime_error("delete failed"); }
const char* poc_checkpoint() {
    static std::string result; std::ostringstream out; trick_MM->write_checkpoint(out); result = out.str(); return result.c_str();
}
void poc_restore(const char* text) {
    ++epoch; std::istringstream in(text);
    // Both MM restore entry points discard the agent's status at this pin.
    // Call the real agent directly so errors cross the binding boundary. These
    // fixtures have no anonymous allocations or STL checkpoint postprocessing.
    trick_MM->reset_memory();
    if (trick_MM->get_CheckPointAgent()->restore(&in)) throw std::runtime_error("checkpoint restore failed");
}
double poc_convert(double value, const char* from, const char* to) {
    auto system = Trick::UdUnits::get_u_system();
    ut_unit* a = ut_parse(system, from, UT_ASCII); ut_unit* b = ut_parse(system, to, UT_ASCII);
    cv_converter* converter = a && b ? ut_get_converter(a, b) : nullptr;
    if (!converter) { if (a) ut_free(a); if (b) ut_free(b); throw std::invalid_argument("incompatible units"); }
    double result = cv_convert_double(converter, value);
    cv_free(converter); ut_free(a); ut_free(b); return result;
}
POCView::POCView(const char* name) : name_(name), id_(find(name)->id), epoch_(epoch) {}
void* POCView::checked() const {
    if (epoch_ != epoch) throw std::runtime_error("stale view: resize or restore");
    auto a = find(name_); if (a->id != id_) throw std::runtime_error("stale view: allocation replaced"); return a->start;
}
int POCView::size() const { checked(); return find(name_)->num; }
double POCView::get(int index) const {
    void* p = checked(); auto a = find(name_);
    if (a->type != TRICK_DOUBLE) throw std::runtime_error("not a double array");
    index_check(index, a->num); return static_cast<double*>(p)[index];
}
void POCView::set(int index, double value) { get(index); static_cast<double*>(checked())[index] = value; }
namespace {
double* field_address(void* p, ALLOC_INFO* a, const char* name) {
    if (a->type != TRICK_STRUCTURED || !a->attr) throw std::runtime_error("not a record");
    for (auto f = static_cast<ATTRIBUTES*>(a->attr); f->name && *f->name; ++f)
        if (!strcmp(name, f->name)) {
            if (f->type != TRICK_DOUBLE || f->num_index) throw std::runtime_error("only scalar double fields in this prototype");
            return reinterpret_cast<double*>(static_cast<char*>(p) + f->offset);
        }
    throw std::runtime_error("unknown field");
}
}
double POCView::field_get(const char* name) const { return *field_address(checked(), find(name_), name); }
void POCView::field_set(const char* name, double value) { *field_address(checked(), find(name_), name) = value; }
double POCView::call_adjust(double value) {
    void* p = checked(); auto a = find(name_);
    if (!a->user_type_name || strcmp(a->user_type_name, "POCModel")) throw std::runtime_error("not POCModel");
    return static_cast<POCModel*>(p)->adjust(value);
}
