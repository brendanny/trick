/* PURPOSE: (Single builtin pointer metadata and checkpoint conformance.) */
#ifndef ICG_BASELINE_POINTERS_HH
#define ICG_BASELINE_POINTERS_HH
using IntegerPointer = int*;
using PointerPair = IntegerPointer[2];
struct PointerModel {
    bool* enabled;
    char* text;
    signed char* signed_code;
    unsigned char* unsigned_code;
    short* small;
    unsigned short* unsigned_small;
    int* count;
    unsigned int* unsigned_count;
    long* large;
    unsigned long* unsigned_large;
    long long* huge;
    unsigned long long* unsigned_huge;
    float* gain;
    double* position; /* trick_units(m) position target */
    char16_t* code;
    IntegerPointer alias;
    PointerPair pairs[2];
    int tail;
};
#endif
