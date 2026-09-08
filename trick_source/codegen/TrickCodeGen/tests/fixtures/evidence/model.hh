/** PURPOSE: (Evidence only.) ICG_IGNORE_TYPES: ((Ignored)) */
#pragma once
#include "dependency.hh"
#define ICG_EVIDENCE_FRIENDS(name) friend class InputProcessor; friend void init_attr##name();
namespace evidence {
class Model {
    ICG_EVIDENCE_FRIENDS(Model)
    friend int init_attrModel(int);
    friend int init_attrModel(double);
    int hidden; /* trick_units(m) */ /* retain both physical comments */
public:
    Dependency value;
};
struct Ignored { int value; };
}
