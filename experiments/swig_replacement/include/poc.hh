#pragma once
#include <string>
#include <vector>

// The generator sees the same layouts. Only allocation declarations are hidden
// from Shiboken's parser, whose generated C++ includes this header normally.
#ifndef POC_GENERATOR
#include "trick/mm_macros.hh"
#endif

struct POCLeft { virtual ~POCLeft() = default; int left = 11; };
struct POCRight { virtual ~POCRight() = default; int right = 29; };
class POCModel : public POCLeft, public POCRight {
public:
    explicit POCModel(double value = 1.0);
    ~POCModel() override;
    double mass;
    double position[3] = {0, 0, 0};
    std::vector<double> samples;
    double adjust(int value);
    double adjust(double value);
    double position_get(int index) const;
    void position_set(int index, double value);
    void sample_push(double value);
    double sample_get(int index) const;
};

class POCAllocated {
#ifndef POC_GENERATOR
    TRICK_MM_INTERFACE(POCAllocated, POCAllocated)
#endif
public:
    explicit POCAllocated(double value = 1.0);
    ~POCAllocated();
    double value;
    bool registered() const;
};

// A prototype checked, borrowed handle. The epoch is deliberately conservative:
// every resize/restore invalidates every existing view. No raw pointer is cached.
class POCView {
public:
    explicit POCView(const char* name);
    double get(int index = 0) const;
    void set(int index, double value);
    int size() const;
    double field_get(const char* field) const;
    void field_set(const char* field, double value);
    double call_adjust(double value);
private:
    std::string name_;
    unsigned int id_;
    unsigned long epoch_;
    void* checked() const;
};

void poc_initialize(const char* library);
void poc_array(const char* name, int count);
void poc_managed(const char* name, double value);
void poc_resize(const char* name, int count);
void poc_erase(const char* name);
const char* poc_checkpoint();
void poc_restore(const char* text);
double poc_convert(double value, const char* from, const char* to);
int poc_live_models();
int poc_live_allocated();
int poc_allocations();
int poc_left(POCLeft* value);
int poc_right(POCRight* value);
long poc_right_offset(POCModel* value);
POCAllocated* poc_new_allocated(double value);
