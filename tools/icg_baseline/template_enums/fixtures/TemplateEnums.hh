/* PURPOSE: (Enum template argument and member metadata conformance.) */
#ifndef ICG_BASELINE_TEMPLATE_ENUMS_HH
#define ICG_BASELINE_TEMPLATE_ENUMS_HH

enum EnumState : int { state_negative = -3, state_zero = 0, state_maximum = 2147483647 };
enum class EnumPhase : int { phase_idle = 0, phase_running = 2, phase_alias = 2 };
namespace enum_fixture {
enum class Mode : unsigned int { mode_zero = 0, mode_high = 2147483647 };
}

template<class T> struct EnumBox {
    T value; /* trick_units(1) selected value */
    T values[2];
    T matrix[2][2];
};
using StateAlias = EnumState;
using PhasePair = EnumPhase[2];
struct EnumConsumers {
    EnumBox<EnumState> plain;
    EnumBox<EnumPhase> scoped;
    EnumBox<enum_fixture::Mode> namespaced;
    EnumBox<PhasePair> array_argument;
    EnumBox<StateAlias> repeated;
    EnumBox<EnumBox<EnumState>> nested;
};

#endif
