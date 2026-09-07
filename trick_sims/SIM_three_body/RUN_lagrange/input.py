"""Three comparable masses rotating in an equilateral triangle about their barycenter."""

import math

dyn_integloop.getIntegrator(trick.Runge_Kutta_4, 18)
masses = [0.75, 1.0, 1.25]
vertices = [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.5, math.sqrt(3.0) / 2.0, 0.0]]
total_mass = sum(masses)
center = [
    sum(masses[i] * vertices[i][axis] for i in range(3)) / total_mass
    for axis in range(3)
]
omega = math.sqrt(float(dyn.system.gravitational_constant) * total_mass)
for body in range(3):
    dyn.system.mass[body] = masses[body]
    position = [vertices[body][axis] - center[axis] for axis in range(3)]
    dyn.system.position[body] = position
    dyn.system.velocity[body] = [-omega * position[1], omega * position[0], 0.0]

exec(open("Modified_data/record.py").read())
# This exact solution is unstable for comparable masses. One orbit is a useful
# analytic check; roundoff/perturbations eventually destroy the triangle.
trick.stop(3.63)
