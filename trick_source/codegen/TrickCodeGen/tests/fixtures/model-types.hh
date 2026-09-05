#pragma once

struct Opaque;

struct Node {
    using Weight = const double;
    Node *next;
    Weight mass = 0.0;
    int counts[2][3];
};
