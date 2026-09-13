/* PURPOSE: (Ordinary enum field metadata and checkpoint conformance.) */
#ifndef ICG_BASELINE_RECORD_ENUMS_HH
#define ICG_BASELINE_RECORD_ENUMS_HH

enum RecordState : int { state_negative = -3, state_zero = 0, state_maximum = 2147483647 };
enum class RecordPhase : int { phase_idle = 0, phase_running = 2, phase_alias = 2 };
namespace record_enum {
enum class Mode : unsigned int { mode_zero = 0, mode_high = 2147483647 };
using PhasePair = RecordPhase[2];
struct Aliases {
    Mode mode;
    PhasePair pairs[2];
    RecordState repeated;
};
}
using RecordStateAlias = RecordState;
struct EnumRecord {
    int lead;
    RecordState state; /* trick_units(1) selected state */
    RecordPhase phase;
    RecordStateAlias states[3];
    RecordPhase phases[2][2];
    record_enum::Mode mode;
    double tail; /* trick_units(m) position */
};

#endif
