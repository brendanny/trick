import gc
import math
import _msd_consumer

checks = []
def expect_error(fn):
    try:
        fn()
    except (RuntimeError, ValueError, TypeError, IndexError):
        return
    raise AssertionError("expected a checked failure")

assert math.isclose(dyn.msd.x_0, 5.0)
assert math.isclose(_msd_consumer.mass(dyn.msd), 1.0)
cross_module_alias = _msd_consumer.echo(dyn.msd)
assert cross_module_alias.m == dyn.msd.m
expect_error(lambda: trick.TMMName(dyn.msd, "interior"))
checks.append("generated_nested_fields_units_and_cross_module_identity")

before = trick.probe_destructions()
temporary = trick.BindingProbe()
assert temporary.thisown
alias = temporary.position
del temporary
gc.collect()
assert trick.probe_destructions() == before  # interior view retains Python owner
alias[0] = trick.attach_units("cm", 250.)
assert alias[0] == 2.5
del alias
gc.collect()
assert trick.probe_destructions() == before + 1
checks.append("python_owner_retained_by_interior_view_and_destroyed_once")

probe = trick.BindingProbe()
probe_alias = probe
array_alias = probe.position
vector_alias = probe.samples
probe.samples = [1., 2.]
class ShrinkDuringConversion:
    def __float__(self):
        probe.samples = []
        return 3.
expect_error(lambda: vector_alias.__setitem__(1, ShrinkDuringConversion()))
assert len(vector_alias) == 0
probe.value = trick.attach_units("g", 2000.)
probe.position = [1., 2., 3.]
probe.samples = [4., 5.]
trick.TMMName(probe, "probe")
assert not probe.thisown and not probe_alias.thisown
assert trick.find_BindingProbe("probe").value == 2.
array_alias[1] = trick.attach_units("cm", 225.)
vector_alias.append(trick.attach_units("cm", 650.))
for i in range(64):  # force vector storage growth without invalidating its handle
    vector_alias.append(float(i))
assert probe.samples[2] == 6.5 and probe.position[1] == 2.25
expect_error(lambda: trick.TMMName(probe, "twice"))
expect_error(lambda: setattr(probe, "value", trick.attach_units("m", 4.)))
expect_error(lambda: setattr(probe, "position", [7., trick.attach_units("kg", 1.), 8.]))
assert list(probe.position) == [1., 2.25, 3.]  # failed conversion is atomic
expect_error(lambda: probe.position[3])
expect_error(lambda: setattr(probe, "position", [1.]))
checks.append("adoption_aliases_units_vector_growth_and_failed_assignment")

candidate = trick.BindingProbe()
before = trick.probe_destructions()
expect_error(lambda: trick.TMMName(candidate, "probe"))
expect_error(lambda: trick.TMMName(candidate, "bad.name"))
assert candidate.thisown
candidate.value = 9.
del candidate
gc.collect()
assert trick.probe_destructions() == before + 1
checks.append("failed_adoption_preserves_python_ownership")

before, records = trick.probe_destructions(), trick.allocation_count()
expect_error(lambda: trick.BindingProbe(TMMName="probe"))
expect_error(lambda: trick.BindingProbe(TMMName=42))
gc.collect()
assert trick.probe_destructions() == before + 2
assert trick.allocation_count() == records
checks.append("failed_named_constructor_reclaims_storage")

named_constructor = trick.BindingProbe(TMMName="constructor_owned")
assert not named_constructor.thisown
named_view = named_constructor.samples
del named_constructor
gc.collect()
named_view.append(3.)
trick.erase("constructor_owned")
expect_error(lambda: len(named_view))
replacement = trick.BindingProbe(TMMName="constructor_owned")
expect_error(lambda: len(named_view))
trick.erase("constructor_owned")
del replacement, named_view
checks.append("named_constructor_delete_and_name_reuse")

ordinary = trick.MSD(7., 2., 0., 5., 0., 5., TMMName="ordinary")
assert ordinary.m == 7.
trick.MSD.default_data(ordinary)
assert ordinary.m == 1. and ordinary.b == .5
ordinary.init()
ordinary_alias = _msd_consumer.echo(ordinary)
del ordinary
gc.collect()
assert ordinary_alias.x == 5.
trick.erase("ordinary")
expect_error(lambda: ordinary_alias.x)
expect_error(lambda: ordinary_alias.state_deriv())
del ordinary_alias
checks.append("ordinary_new_adoption_and_method_invalidation")
