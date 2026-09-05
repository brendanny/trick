#include "model-types.hh"

using Handle = Node *;

struct Model {
    const Handle head = nullptr;
    Opaque *opaque;
    int &external;
};
