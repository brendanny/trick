/* PURPOSE: (Enum pointer metadata, identity and symbolic checkpoint conformance.) */
#ifndef ICG_BASELINE_ENUM_POINTERS_HH
#define ICG_BASELINE_ENUM_POINTERS_HH

enum PointerState : int { pointer_negative = -3, pointer_zero = 0, pointer_maximum = 2147483647 };
enum class PointerPhase : int { pointer_idle = 0, pointer_running = 2, pointer_alias = 2 };
namespace enum_pointer {
enum class Mode : unsigned int { pointer_mode_zero = 0, pointer_mode_high = 2147483647 };
}
using StatePointer = PointerState*;
using PhasePointers = PointerPhase*[2];
struct EnumPointerModel {
    int lead;
    PointerState* state; /* trick_units(1) state target */
    PointerPhase* phase;
    enum_pointer::Mode* mode;
    StatePointer alias;
    PointerState* states[3];
    PhasePointers matrix[2];
    PointerState local;
    int tail;
};
namespace enum_pointer {
struct Targets {
    PointerState states[3];
    PointerPhase phases[3];
    Mode modes[3];
};
}
#endif
