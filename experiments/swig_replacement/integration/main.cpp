#include "runtime.hh"
#include "models.hh"
#include "trick/IPPython.hh"
#include "trick/RK4_Integrator.hh"
#include <Python.h>
#include <cmath>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <thread>

Trick::Integrator* trick_curr_integ = nullptr;
extern double integration_stop_time;
// Command-line and termination service adapters for the standalone driver.
// IPPython itself, including its GIL guards and restart/shutdown paths, is real.
extern "C" int command_line_args_get_argc() { return 0; }
extern "C" char** command_line_args_get_argv() { return nullptr; }
extern "C" const char* command_line_args_get_input_file() { return ""; }
extern "C" int exec_terminate_with_return(int code, const char*, int, const char* message) {
    throw std::runtime_error(std::string(message) + " (status " + std::to_string(code) + ")");
}
static void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}
static std::string read(const char* filename) {
    std::ifstream input(filename);
    if (!input) throw std::runtime_error(std::string("cannot read ") + filename);
    return {std::istreambuf_iterator<char>(input), {}};
}
static MSD& model() { return static_cast<BindingDynamics*>(binding::named("dyn")->start)->msd; }
static void advance(int steps) {
    for (int step = 0; step < steps; ++step) {
        int pass = 0;
        do {
            require(model().state_deriv() == 0, "derivative job failed");
            pass = model().state_integ();
        } while (pass != 0);
    }
    model().state_deriv();
}
int main(int argc, char** argv) {
    if (argc != 7) { std::cerr << "usage: poc_msd CORE_DSO MODEL_DSO INPUT CONTRACTS AFTER_RESTORE CLEANUP\n"; return 2; }
    Trick::IPPython ip;
    try {
        binding::initialize(argv[1], argv[2]);
        auto dynamics = trick_MM->declare_var("BindingDynamics dyn");
        require(dynamics != nullptr, "cannot allocate dynamics");
        MSD::default_data(model());
        ip.input_file = argv[3];
        require(ip.init() == 0, "IPPython init failed");
        require(ip.parse(read(argv[4])) == 0, "binding contracts failed");
        int worker_status = -1;
        std::thread worker([&] { worker_status = ip.parse("assert dyn.msd.m == 1.0\nworker_ran = True"); });
        worker.join();
        require(worker_status == 0, "worker IPPython parse failed");
        require(ip.parse("assert worker_ran") == 0, "worker result missing");
        require(model().init() == 0, "model init failed");
        const double dt = .01;
        const int steps = static_cast<int>(std::llround(integration_stop_time / dt));
        require(steps > 1 && std::abs(steps * dt - integration_stop_time) < 1e-12, "stop must be an integral number of steps");
        const int split = steps / 2;
        double final_x, final_v, replay_x, replay_v;
        {
            Trick::RK4_Integrator integrator(2, dt);
            trick_curr_integ = &integrator;
            advance(split);
            require(ip.parse("snapshot = trick.checkpoint()\nold_dyn = dyn\nold_msd = dyn.msd\nold_samples = probe.samples") == 0, "checkpoint failed");
            advance(steps - split);
            final_x = model().x; final_v = model().v;
            require(ip.parse("trick.restore(snapshot)") == 0, "restore failed");
            require(ip.restart() == 0, "IPPython restart failed");
            require(ip.parse(read(argv[5])) == 0, "post-restore contracts failed");
            integrator.time = split * dt;
            advance(steps - split);
            replay_x = model().x; replay_v = model().v;
            trick_curr_integ = nullptr;
        }
        // Closed-form solution independently checks the actual MSD/RK4 jobs.
        const double equilibrium = model().F / model().k;
        const double omega = std::sqrt(model().k / model().m);
        const double amplitude = model().x_0 - equilibrium;
        const double t = integration_stop_time;
        const double expected_x = equilibrium + amplitude * std::cos(omega*t) + model().v_0/omega * std::sin(omega*t);
        const double expected_v = -amplitude*omega * std::sin(omega*t) + model().v_0*std::cos(omega*t);
        require(model().b == 0., "analytic oracle requires the no-damping input");
        require(std::abs(final_x-expected_x) < 2e-8 && std::abs(final_v-expected_v) < 2e-8, "RK4 disagrees with analytic MSD trajectory");
        require(std::abs(final_x-replay_x) < 1e-12 && std::abs(final_v-replay_v) < 1e-12, "checkpoint continuation differs");
        require(model().shutdown() == 0, "model shutdown job failed");
        require(ip.parse(read(argv[6])) == 0, "cleanup contracts failed");
        binding::erase("dyn");
        require(ip.parse("expect_error(lambda: dyn.msd.x)") == 0, "deleted root still accessible");
        require(ip.shutdown() == 0 && !Py_IsInitialized(), "IPPython did not finalize");
        require(binding::allocation_count() == 0, "MM allocations remain");
        require(probe_constructions() == probe_destructions(), "probe destructor imbalance");
        std::cout << std::setprecision(17) << "INTEGRATION_RESULT={\"status\":\"pass\",\"steps\":" << steps
                  << ",\"x\":" << final_x << ",\"v\":" << final_v
                  << ",\"analytic_x_error\":" << std::abs(final_x-expected_x)
                  << ",\"analytic_v_error\":" << std::abs(final_v-expected_v)
                  << ",\"restart_x_error\":" << std::abs(final_x-replay_x)
                  << ",\"restart_v_error\":" << std::abs(final_v-replay_v)
                  << ",\"remaining_allocations\":0,\"probe_constructions\":" << probe_constructions()
                  << ",\"probe_destructions\":" << probe_destructions() << "}\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "Integration failed: " << error.what() << '\n';
        // Each failure is isolated by run.py; avoid unsafe teardown of partially
        // initialized interpreter state on this error path.
        return 1;
    }
}
