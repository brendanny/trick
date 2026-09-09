/* PURPOSE: (Observe legacy sign extension without declaring numeric parity.) */
#ifndef ICG_UNSIGNED_NARROW_HH
#define ICG_UNSIGNED_NARROW_HH

namespace icg_rejected {
enum class Boolean : bool { zero = false, one = true };
enum class Byte : unsigned char { valid = 127, middle = 128, maximum = 255 };
enum class Word : unsigned short { valid = 32767, middle = 32768, maximum = 65535 };
}

#endif
