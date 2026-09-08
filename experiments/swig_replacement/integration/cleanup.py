trick.erase("probe")
expect_error(lambda: probe.value)
# Invalid input must surface despite MemoryManager's unconditional return code.
expect_error(lambda: trick.restore("not_a_type broken;"))
# This malformed restore resets manager allocations first, so dyn is already
# gone. Recreate it only to exercise driver-side direct deletion after cleanup.
# A named constructor leaves the object under MM ownership.
dyn = trick.BindingDynamics(TMMName="dyn")
checks.append("invalid_checkpoint_state_and_error_translation")
del probe, probe_alias, array_alias, vector_alias, old_dyn, old_msd, old_samples, cross_module_alias
gc.collect()
print("INTEGRATION_CHECKS=" + __import__("json").dumps(checks), flush=True)
