#pragma once
#include "msd.hh"
#include "trick/mm_macros.hh"
#include <vector>

// Minimal simulation-object shell. The production S_define translator and
// Executive are deliberately not replaced by this hand-authored driver.
struct BindingDynamics {
    MSD msd; /**< trick_units(--) Existing simulation model. */
};

// A lifecycle/container adversary alongside the unmodified MSD model.
struct BindingProbe {
    TRICK_MM_INTERFACE(BindingProbe, BindingProbe)
    BindingProbe();
    ~BindingProbe();
    double value = 1.; /**< trick_units(kg) Scalar with units. */
    double position[3] = {}; /**< trick_units(m) Fixed array. */
    std::vector<double> samples; /**< trick_units(m) Live vector. */
};

int probe_constructions();
int probe_destructions();
