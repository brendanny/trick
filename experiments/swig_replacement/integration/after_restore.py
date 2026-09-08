expect_error(lambda: old_dyn.msd.x)
expect_error(lambda: old_msd.x)
expect_error(lambda: cross_module_alias.m)
expect_error(lambda: old_samples[0])
expect_error(lambda: array_alias[0])
expect_error(lambda: vector_alias.append(9.))
# IPPython.restart has rebound both named roots through generated cast functions.
assert dyn is not old_dyn
assert probe.value == 2.
assert list(probe.position) == [1., 2.25, 3.]
assert list(probe.samples) == [4., 5., 6.5] + [float(i) for i in range(64)]
assert _msd_consumer.mass(dyn.msd) == 1.
checks.append("real_mm_stl_checkpoint_and_ippython_restart_invalidation")
