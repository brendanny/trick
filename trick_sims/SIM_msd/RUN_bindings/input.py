"""Headless MSD input for the binding integration experiment.

Only model settings and stop time: it can also be used by the normal simulation.
No display, wall-clock synchronization, or variable-server client is launched.
"""
dyn.msd.m = trick.attach_units("kg", 1.0)
dyn.msd.k = trick.attach_units("N/m", 2.0)
dyn.msd.b = 0.0
dyn.msd.F = trick.attach_units("N", 5.0)
dyn.msd.v_0 = 0.0
dyn.msd.x_0 = trick.attach_units("cm", 500.0)
trick.stop(2.0)
