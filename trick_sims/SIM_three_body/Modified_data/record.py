"""Record accepted states and conservation diagnostics using Trick's CSV recorder."""

recording = trick.DRAscii("three_body")
recording.set_freq(trick.DR_Always)
recording.set_cycle(0.01)
recording.set_ascii_double_format("%.17g")
for field in (
    "gravitational_constant",
    "kinetic_energy",
    "potential_energy",
    "total_energy",
    "closest_distance",
):
    recording.add_variable("dyn.system." + field)
for body in range(3):
    recording.add_variable("dyn.system.mass[%d]" % body)
    for field in ("position", "velocity", "acceleration"):
        for axis in range(3):
            recording.add_variable("dyn.system.%s[%d][%d]" % (field, body, axis))
for field in ("momentum", "angular_momentum", "center_of_mass"):
    for axis in range(3):
        recording.add_variable("dyn.system.%s[%d]" % (field, axis))
trick.add_data_record_group(recording, trick.DR_Buffer)
