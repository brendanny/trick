#include "trick/MemoryManager.hh"
#ifdef USE_ER7_UTILS_INTEGRATORS
#include "er7_utils/integration/core/include/single_cycle_integration_controls.hh"
#include "er7_utils/integration/euler/include/euler_first_order_ode_integrator.hh"
#else
#include "trick/Euler_Integrator.hh"
#endif
#include <cmath>
#include <cstdlib>

// Only the fatal diagnostic boundary is external to this closed subsystem.
extern "C" int exec_terminate_with_return(int code, const char*, int, const char*) { std::exit(code ? code : 1); }

int main()
{
    Trick::MemoryManager memory;
    double state            = 1.0;
    const double derivative = 2.0;
#ifdef USE_ER7_UTILS_INTEGRATORS
    er7_utils::SingleCycleIntegrationControls controls(1);
    er7_utils::EulerFirstOrderODEIntegrator integrator(1, controls);
    integrator.integrate(0.25, 1, &derivative, &state);
#else
    Trick::Euler_Integrator integrator(1, 0.25);
    integrator.integrate_1st_order_ode(&derivative, &state);
#endif
    return std::abs(state - 1.5) < 1e-12 ? 0 : 1;
}
