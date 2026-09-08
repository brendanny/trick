#include "models.hh"
namespace { int constructed = 0, destroyed = 0; }
BindingProbe::BindingProbe() { ++constructed; }
BindingProbe::~BindingProbe() { ++destroyed; }
int probe_constructions() { return constructed; }
int probe_destructions() { return destroyed; }
