# Three-body simulation

`SIM_three_body` integrates three Newtonian point masses in an inertial Cartesian
frame. Every body accelerates under the gravity of both other bodies. All masses
may be comparable, and all three position and velocity vectors may be specified
in three dimensions. No central body is fixed and no restricted-three-body
approximation is used.

## Build and run

From this directory, with a built Trick installation on `PATH`:

```sh
trick-CP
./S_main_$(trick-gte TRICK_HOST_CPU).exe RUN_figure_eight/input.py
./S_main_$(trick-gte TRICK_HOST_CPU).exe RUN_lagrange/input.py
python3 tests/test_sim.py
```

Both runs execute without a GUI or real-time pacing. Trick writes
`RUN_*/log_three_body.csv`, containing time, masses, positions, velocities,
accelerations, energies, total linear and angular momentum, center of mass, and
the closest pair separation. CSV doubles retain 17 significant digits. The test
script uses only Python's standard library and runs the generated executable in
temporary output directories. The example and its regressions are also included
in the repository's `test_sims.yml` workflow.

For a trajectory and energy plot using Trick's data-products tools:

```sh
trick-qp RUN_figure_eight DP_Product/DP_three_body.xml
```

## Included cases

| Run | Masses | Initial configuration | Duration |
| --- | --- | --- | --- |
| `RUN_figure_eight` | `1 : 1 : 1` | Equal-mass figure-eight choreography | 20 time units, about three periods |
| `RUN_lagrange` | `0.75 : 1 : 1.25` | Rotating equilateral triangle of side length 1 | 3.63 time units, about one period |

The figure-eight initial conditions and approximate period `6.32591398` are from
Figure 1 of Chenciner and Montgomery,
[A remarkable periodic solution of the three-body problem in the case of equal masses](https://arxiv.org/abs/math/0011268).
The supplied decimal initial conditions approximate the periodic orbit.

The Lagrange case rotates about the **mass-weighted** center of mass with angular
speed `sqrt(G * (m0 + m1 + m2) / side_length^3)`. Each mass therefore follows a
different circle. This is an exact solution for arbitrary positive masses, but
the comparable-mass triangle is unstable to perturbations: it is an analytic
validation case over the supplied duration, not a promise of long-term stability.

## Model and integration

For each pair `i < j`, with `d = position[j] - position[i]`, the model adds

```text
acceleration[i] += G * mass[j] * d / |d|^3
acceleration[j] -= G * mass[i] * d / |d|^3
```

This gives equal and opposite pair forces even when masses differ. One Trick
RK4 integrator advances all 18 states together, using a step of `0.001`. Each
derivative stage evaluates the forces using all three bodies at that same stage.
The `post_integration` job recomputes acceleration and diagnostics at the accepted
state. The recorder samples every `0.01` time units.

The potential is exactly `-sum(G * mass[i] * mass[j] / distance[i,j])` over the
three distinct pairs. No softening, collisions, merging, finite body radii,
relativity, or external forces are modeled. Masses and `G` are constant during
a run. Positive finite masses, `G`, and `minimum_distance` are required.
Non-finite states and separations at or below `minimum_distance` terminate the
simulation with a nonzero exit status.

This is a fixed-step educational example. Close encounters require smaller
steps; the distance guard checks sampled integration stages and cannot detect
every encounter between them. It does not replace collision detection or
regularization. RK4 is not symplectic, and conservation error can accumulate over
long integrations. General three-body trajectories can be chaotic. Check energy,
momentum, and step convergence for new initial conditions.

## Change the initial conditions or scale

The examples use normalized gravitational units with `G = 1` and order-one
masses and distances. The C++ field annotations describe the physical dimensions
using SI labels so Trick can expose and record them; the example numbers are
scaled coordinates, not a physical SI system with the measured value of `G`.

To model an SI system, set `dyn.system.gravitational_constant = 6.67430e-11`,
enter masses in kg, positions in m, and velocities in m/s. Choose the integration
step, recording cycle, stop time, and distance threshold to match those scales.
For example, to rescale the default figure eight to mass scale `M` and length
scale `L`, use `T = sqrt(L**3 / (G * M))`: multiply positions by `L`, velocities
by `L/T`, masses by `M`, and all times by `T`.

Python inputs can assign `dyn.system.mass[body]`,
`dyn.system.position[body][axis]`, and `dyn.system.velocity[body][axis]` directly.
The model preserves your inertial frame; it does not silently recenter the state.
To change the step after selecting the integrator:

```python
dyn_integloop.set_integ_cycle(0.0005)
```

## Regression coverage

The tests check the equal-mass figure eight over three periods, the comparable-
mass triangle against its analytic trajectory, a tilted/translated/steadily
moving version of that triangle, and a non-equilateral `0.9 : 1 : 1.1` case.
They independently reconstruct forces, energy, momentum, angular momentum, and
center of mass from recorded states. They also check RK4 step convergence,
invalid inputs, and termination during a close encounter. No golden trajectory
file or third-party Python numerical package is required.
