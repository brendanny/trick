/* PURPOSE: (Record pointer metadata and cyclic checkpoint identity.) */
#ifndef ICG_BASELINE_RECORD_POINTERS_HH
#define ICG_BASELINE_RECORD_POINTERS_HH

namespace record_pointer {
struct Peer;
struct Node {
    int value;
    Node* next; /* trick_units(1) next node */
    Peer* peer;
};
struct Peer {
    double value;
    Node* owner;
};
}
using NodePointer = record_pointer::Node*;
using NodePair = NodePointer[2];
struct RecordPointerModel {
    int lead;
    NodePointer head;
    record_pointer::Peer* peer;
    NodePointer alias;
    NodePointer nodes[3];
    NodePair matrix[2];
    int tail;
};
#endif
