#include "ThreeBody.hh"

#include "trick/exec_proto.h"
#include "trick/integrator_c_intf.h"

#include <cmath>
#include <limits>

namespace
{
    int fail(const char* message) { return exec_terminate_with_return(1, __FILE__, __LINE__, message); }
}

int ThreeBody::default_data()
{
    // Figure-eight initial conditions in units where G = m = 1.
    // See Chenciner and Montgomery (2000), Figure 1 (README.md).
    gravitational_constant = 1.0;
    minimum_distance       = 1.0e-6;
    for (int body = 0; body < 3; ++body)
    {
        mass[body] = 1.0;
        for (int axis = 0; axis < 3; ++axis)
        {
            position[body][axis]     = 0.0;
            velocity[body][axis]     = 0.0;
            acceleration[body][axis] = 0.0;
        }
    }
    position[0][0] = 0.97000436;
    position[0][1] = -0.24308753;
    position[1][0] = -position[0][0];
    position[1][1] = -position[0][1];
    velocity[0][0] = velocity[1][0] = 0.466203685;
    velocity[0][1] = velocity[1][1] = 0.432365730;
    velocity[2][0]                  = -2.0 * velocity[0][0];
    velocity[2][1]                  = -2.0 * velocity[0][1];
    return 0;
}

int ThreeBody::initialize()
{
    if (!std::isfinite(gravitational_constant) || gravitational_constant <= 0.0)
    {
        return fail("ThreeBody: gravitational_constant must be finite and positive.");
    }
    if (!std::isfinite(minimum_distance) || minimum_distance <= 0.0)
    {
        return fail("ThreeBody: minimum_distance must be finite and positive.");
    }
    for (int body = 0; body < 3; ++body)
    {
        if (!std::isfinite(mass[body]) || mass[body] <= 0.0)
        {
            return fail("ThreeBody: each mass must be finite and positive.");
        }
    }
    return diagnostics();
}

int ThreeBody::derivative()
{
    for (int body = 0; body < 3; ++body)
    {
        for (int axis = 0; axis < 3; ++axis)
        {
            if (!std::isfinite(position[body][axis]) || !std::isfinite(velocity[body][axis]))
            {
                return fail("ThreeBody: non-finite state; reduce the integration step.");
            }
            acceleration[body][axis] = 0.0;
        }
    }

    // Evaluate each pair once, using the SAME integration stage for all bodies.
    // Both bodies respond; unequal masses have unequal accelerations.
    closest_distance = std::numeric_limits<double>::max();
    for (int first = 0; first < 3; ++first)
    {
        for (int second = first + 1; second < 3; ++second)
        {
            double displacement[3];
            for (int axis = 0; axis < 3; ++axis)
            {
                displacement[axis] = position[second][axis] - position[first][axis];
            }
            const double distance = std::hypot(std::hypot(displacement[0], displacement[1]), displacement[2]);
            if (!std::isfinite(distance) || distance <= minimum_distance)
            {
                return fail("ThreeBody: pair separation is at or below minimum_distance, or non-finite.");
            }
            if (distance < closest_distance)
            {
                closest_distance = distance;
            }
            const double factor = gravitational_constant / distance / distance;
            for (int axis = 0; axis < 3; ++axis)
            {
                const double component      = factor * (displacement[axis] / distance);
                acceleration[first][axis]  += mass[second] * component;
                acceleration[second][axis] -= mass[first] * component;
            }
        }
    }
    for (int body = 0; body < 3; ++body)
    {
        for (int axis = 0; axis < 3; ++axis)
        {
            if (!std::isfinite(acceleration[body][axis]))
            {
                return fail("ThreeBody: non-finite acceleration; check the scales and integration step.");
            }
        }
    }
    return 0;
}

int ThreeBody::integrate_state()
{
    // One 18-state system: [x,y,z,vx,vy,vz] for each of the three bodies.
    for (int body = 0; body < 3; ++body)
    {
        for (int axis = 0; axis < 3; ++axis)
        {
            const unsigned int index = 6 * body + axis;
            load_indexed_state(index, position[body][axis]);
            load_indexed_state(index + 3, velocity[body][axis]);
            load_indexed_deriv(index, velocity[body][axis]);
            load_indexed_deriv(index + 3, acceleration[body][axis]);
        }
    }
    const int step = integrate();
    for (int body = 0; body < 3; ++body)
    {
        for (int axis = 0; axis < 3; ++axis)
        {
            const unsigned int index = 6 * body + axis;
            position[body][axis]     = unload_indexed_state(index);
            velocity[body][axis]     = unload_indexed_state(index + 3);
        }
    }
    return step;
}

int ThreeBody::diagnostics()
{
    // Refresh acceleration and separation at the accepted state, not the last RK stage.
    const int status = derivative();
    if (status != 0)
    {
        return status;
    }
    kinetic_energy = potential_energy = 0.0;
    double total_mass                 = 0.0;
    for (int axis = 0; axis < 3; ++axis)
    {
        momentum[axis] = angular_momentum[axis] = center_of_mass[axis] = 0.0;
    }
    for (int body = 0; body < 3; ++body)
    {
        total_mass += mass[body];
        for (int axis = 0; axis < 3; ++axis)
        {
            kinetic_energy         += 0.5 * mass[body] * velocity[body][axis] * velocity[body][axis];
            momentum[axis]         += mass[body] * velocity[body][axis];
            center_of_mass[axis]   += mass[body] * position[body][axis];
            const int next          = (axis + 1) % 3;
            const int last          = (axis + 2) % 3;
            angular_momentum[axis] += mass[body]
                * (position[body][next] * velocity[body][last] - position[body][last] * velocity[body][next]);
        }
        for (int other = body + 1; other < 3; ++other)
        {
            const double distance
                = std::hypot(std::hypot(position[other][0] - position[body][0], position[other][1] - position[body][1]),
                             position[other][2] - position[body][2]);
            potential_energy -= gravitational_constant * mass[body] * mass[other] / distance;
        }
    }
    total_energy = kinetic_energy + potential_energy;
    if (!std::isfinite(total_energy) || !std::isfinite(total_mass))
    {
        return fail("ThreeBody: non-finite energy or total mass; check the input scales.");
    }
    for (int axis = 0; axis < 3; ++axis)
    {
        center_of_mass[axis] /= total_mass;
        if (!std::isfinite(momentum[axis]) || !std::isfinite(angular_momentum[axis])
            || !std::isfinite(center_of_mass[axis]))
        {
            return fail("ThreeBody: non-finite diagnostic; check the input scales.");
        }
    }
    return 0;
}
