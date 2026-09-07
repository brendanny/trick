"""End-to-end physics regressions. Build with trick-CP, then run this file.

Only the Python standard library is required. Every trajectory comes from the
generated Trick executable, including the step-size convergence check.
"""

import csv
import math
import subprocess
import tempfile
import unittest
from pathlib import Path

SIM = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open(newline="") as stream:
        reader = csv.reader(stream)
        names = [name.split(" {")[0].strip() for name in next(reader)]
        return [dict(zip(names, map(float, row))) for row in reader]


def scalar(row, name):
    return row["dyn.system." + name]


def vector(row, name):
    return [scalar(row, "%s[%d]" % (name, axis)) for axis in range(3)]


def norm(values):
    return math.sqrt(sum(value * value for value in values))


class ThreeBodyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        binaries = sorted(SIM.glob("S_main_*.exe"))
        if len(binaries) != 1:
            raise RuntimeError(
                "Build SIM_three_body with trick-CP; expected one S_main_*.exe"
            )
        cls.binary = binaries[0]

    def run_sim(self, case="figure_eight", extra="", stop=None, error=None):
        with tempfile.TemporaryDirectory(prefix="three_body_") as directory:
            directory = Path(directory)
            script = directory / "input.py"
            text = 'exec(open("RUN_%s/input.py").read())\n' % case
            text += "trick.var_server_set_enabled(False)\n"
            text += extra + "\n"
            if stop is not None:
                text += "trick.stop(%r)\n" % stop
            script.write_text(text)
            result = subprocess.run(
                [str(self.binary), str(script), "-O", str(directory / "output")],
                cwd=SIM,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=60,
                check=False,
            )
            if error is not None:
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn(error, result.stdout)
                return None
            self.assertEqual(result.returncode, 0, result.stdout)
            rows = read_csv(directory / "output/log_three_body.csv")
            self.assertGreaterEqual(len(rows), 2)
            self.assertTrue(
                all(math.isfinite(value) for row in rows for value in row.values())
            )
            return rows

    def check_physics(self, rows, energy_tolerance=1e-8):
        first = rows[0]
        initial_energy = scalar(first, "total_energy")
        initial_momentum = vector(first, "momentum")
        initial_angular = vector(first, "angular_momentum")
        initial_center = vector(first, "center_of_mass")
        masses = [scalar(first, "mass[%d]" % i) for i in range(3)]
        total_mass = sum(masses)
        max_energy_error = 0.0
        for row in rows:
            time = row["sys.exec.out.time"] - first["sys.exec.out.time"]
            positions = [vector(row, "position[%d]" % i) for i in range(3)]
            velocities = [vector(row, "velocity[%d]" % i) for i in range(3)]
            # Independently reconstruct observables and forces from the logged state.
            kinetic = sum(0.5 * masses[i] * norm(velocities[i]) ** 2 for i in range(3))
            potential = 0.0
            constant = scalar(row, "gravitational_constant")
            for i in range(3):
                expected_acceleration = [0.0] * 3
                for j in range(3):
                    if i == j:
                        continue
                    displacement = [positions[j][k] - positions[i][k] for k in range(3)]
                    distance = norm(displacement)
                    if j > i:
                        potential -= constant * masses[i] * masses[j] / distance
                    for k in range(3):
                        expected_acceleration[k] += (
                            constant * masses[j] * displacement[k] / distance**3
                        )
                self.assertLess(
                    norm([
                        a - b
                        for a, b in zip(
                            vector(row, "acceleration[%d]" % i), expected_acceleration
                        )
                    ]),
                    1e-10,
                )
            self.assertAlmostEqual(scalar(row, "kinetic_energy"), kinetic, delta=1e-10)
            self.assertAlmostEqual(
                scalar(row, "potential_energy"), potential, delta=1e-10
            )
            self.assertAlmostEqual(
                scalar(row, "total_energy"), kinetic + potential, delta=1e-10
            )
            max_energy_error = max(
                max_energy_error,
                abs((kinetic + potential - initial_energy) / initial_energy),
            )
            for k in range(3):
                momentum = sum(masses[i] * velocities[i][k] for i in range(3))
                center = sum(masses[i] * positions[i][k] for i in range(3)) / total_mass
                a, b = (k + 1) % 3, (k + 2) % 3
                angular = sum(
                    masses[i]
                    * (
                        positions[i][a] * velocities[i][b]
                        - positions[i][b] * velocities[i][a]
                    )
                    for i in range(3)
                )
                self.assertAlmostEqual(
                    scalar(row, "momentum[%d]" % k), momentum, delta=1e-10
                )
                self.assertAlmostEqual(
                    scalar(row, "center_of_mass[%d]" % k), center, delta=1e-10
                )
                self.assertAlmostEqual(
                    scalar(row, "angular_momentum[%d]" % k), angular, delta=1e-10
                )
                self.assertAlmostEqual(momentum, initial_momentum[k], delta=1e-9)
                self.assertAlmostEqual(angular, initial_angular[k], delta=1e-8)
                self.assertAlmostEqual(
                    center,
                    initial_center[k] + time * initial_momentum[k] / total_mass,
                    delta=1e-9,
                )
        self.assertLess(max_energy_error, energy_tolerance)
        return max_energy_error

    def lagrange_error(self, rows):
        first = rows[0]
        total_mass = sum(scalar(first, "mass[%d]" % i) for i in range(3))
        center = vector(first, "center_of_mass")
        drift = [value / total_mass for value in vector(first, "momentum")]
        separation = norm([
            a - b
            for a, b in zip(vector(first, "position[0]"), vector(first, "position[1]"))
        ])
        omega = math.sqrt(
            scalar(first, "gravitational_constant") * total_mass / separation**3
        )
        max_error = 0.0
        for row in rows:
            time = row["sys.exec.out.time"] - first["sys.exec.out.time"]
            for i in range(3):
                for k in range(3):
                    r = scalar(first, "position[%d][%d]" % (i, k)) - center[k]
                    v = scalar(first, "velocity[%d][%d]" % (i, k)) - drift[k]
                    expected = center[k] + drift[k] * time + r * math.cos(omega * time)
                    expected += v * math.sin(omega * time) / omega
                    max_error = max(
                        max_error,
                        abs(scalar(row, "position[%d][%d]" % (i, k)) - expected),
                    )
        return max_error

    def test_equal_mass_figure_eight(self):
        rows = self.run_sim()
        self.assertAlmostEqual(rows[-1]["sys.exec.out.time"], 20.0)
        error = self.check_physics(rows)
        # Published period is approximate; use the nearest recorded sample.
        period = 6.32591398
        for cycle in (1, 2, 3):
            row = min(
                rows, key=lambda value: abs(value["sys.exec.out.time"] - cycle * period)
            )
            time_error = abs(row["sys.exec.out.time"] - cycle * period)
            for i in range(3):
                delta = [
                    a - b
                    for a, b in zip(
                        vector(row, "position[%d]" % i),
                        vector(rows[0], "position[%d]" % i),
                    )
                ]
                self.assertLess(norm(delta), 2.0 * time_error + 2e-6)
        print("figure eight: max relative energy error = %.3g" % error)

    def test_comparable_mass_lagrange(self):
        rows = self.run_sim("lagrange")
        self.assertAlmostEqual(rows[-1]["sys.exec.out.time"], 3.63)
        self.check_physics(rows)
        error = self.lagrange_error(rows)
        self.assertLess(error, 1e-7)
        print("Lagrange: max position error = %.3g" % error)

    def test_inclined_translated_moving_system(self):
        extra = """
angle = 0.7
for body in range(3):
    p = [float(dyn.system.position[body][k]) for k in range(3)]
    v = [float(dyn.system.velocity[body][k]) for k in range(3)]
    dyn.system.position[body] = [p[0] + 2.0, math.cos(angle)*p[1] - 3.0, math.sin(angle)*p[1] + 1.0]
    dyn.system.velocity[body] = [v[0] + 0.2, math.cos(angle)*v[1] - 0.1, math.sin(angle)*v[1] + 0.15]
"""
        rows = self.run_sim("lagrange", extra)
        self.check_physics(rows)
        self.assertLess(self.lagrange_error(rows), 1e-7)

    def test_unequal_non_equilateral_system(self):
        rows = self.run_sim(extra="dyn.system.mass = [0.9, 1.0, 1.1]", stop=5.0)
        self.assertAlmostEqual(rows[-1]["sys.exec.out.time"], 5.0)
        self.check_physics(rows, energy_tolerance=1e-7)

    def test_rk4_step_convergence(self):
        errors = []
        for step in (0.02, 0.01):
            rows = self.run_sim(
                "lagrange", "dyn_integloop.set_integ_cycle(%r)" % step, stop=1.0
            )
            # Only compare the endpoint; the recorder runs faster than the coarse integrator.
            errors.append(self.lagrange_error([rows[0], rows[-1]]))
        ratio = errors[0] / errors[1]
        self.assertGreater(ratio, 12.0)
        self.assertLess(ratio, 20.0)
        print("RK4 error reduction on halving dt = %.3g" % ratio)

    def test_invalid_inputs(self):
        cases = [
            ("mass[0]", "0.0", "each mass"),
            ("mass[1]", "-1.0", "each mass"),
            ("mass[2]", 'float("nan")', "each mass"),
            ("mass[0]", 'float("inf")', "each mass"),
            ("gravitational_constant", "0.0", "gravitational_constant"),
            ("minimum_distance", "-1.0", "minimum_distance"),
            ("position[1]", "[0.97000436, -0.24308753, 0.0]", "pair separation"),
            ("velocity[0][2]", 'float("nan")', "non-finite state"),
        ]
        for field, value, error in cases:
            with self.subTest(field=field, value=value):
                self.run_sim(
                    extra="dyn.system.%s = %s" % (field, value), stop=0.01, error=error
                )

    def test_close_encounter_stops(self):
        extra = """
dyn.system.position = [[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
dyn.system.velocity = [[0.0, 0.0, 0.0]] * 3
dyn.system.minimum_distance = 0.99
"""
        self.run_sim(extra=extra, stop=1.0, error="pair separation")


if __name__ == "__main__":
    unittest.main(verbosity=2)
