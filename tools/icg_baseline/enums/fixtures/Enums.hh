/* PURPOSE: (Scoped and unscoped enum metadata conformance.) */
#ifndef ICG_ENUMS_HH
#define ICG_ENUMS_HH

enum class GlobalMode { off = -3, on = 7 };

namespace icg_enum {
enum class Opaque : unsigned;
enum Plain { minimum = -2147483647 - 1, maximum = 2147483647 };
enum class Signed : long long { negative = -21, zero = 0, alias = 0, positive = 3 };
enum struct Byte : unsigned char { zero = 0, last = 127 };
enum class Word : unsigned short { zero = 0, last = 32767 };
enum class DWord : unsigned int { zero = 0, last = 2147483647 };
enum class QWord : unsigned long long { last = 2147483647 };
enum class Empty {};

inline namespace v1 {
enum class Mode { off, on };
struct Owner {
    enum class State : short { idle = -1, active = 2 };
    int count;
private:
    enum class Hidden { secret };
};
}
}

#endif
