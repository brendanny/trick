"""Three equal masses following the figure-eight orbit; defaults are set in C++."""

dyn_integloop.getIntegrator(trick.Runge_Kutta_4, 18)
exec(open("Modified_data/record.py").read())
trick.stop(20.0)
