#pragma once

#include "trick2/registry.hpp"
#include "trick2/simulation.hpp"

#include <chrono>
#include <cmath>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string_view>

namespace example
{

    // Model ownership, registration, scheduling, and observation are ordinary C++.
    // This function owns no model and makes no background threads.
    template <class Model, class Advance>
    int run_oscillator(int argc, char** argv, Model& model, trick2::TypeDescriptor schema, Advance advance)
    {
        const bool verify = argc == 2 && std::string_view(argv[1]) == "--verify";
        if (argc > 2 || (argc == 2 && !verify))
        {
            std::cerr << "Usage: " << argv[0] << " [--verify]\n";
            return 2;
        }

        using namespace std::chrono_literals;
        trick2::Registry registry;
        auto registration = registry.expose("oscillator", model, schema);
        const auto handle = registration.handle();
        // Configuration is a checked write through the same schema used for output.
        registry.write(handle, 1, 1.0);
        registry.write(handle, 2, 0.0);

        trick2::Simulation simulation;
        std::size_t observations = 0;
        double max_error         = 0.0;
        if (!verify)
        {
            std::cout << "time_s,position_m,velocity_m_per_s\n" << std::setprecision(12);
        }
        const auto dynamics = simulation.every(
            1ms, trick2::Phase::dynamics,
            [&](const trick2::StepContext& context)
            {
                const double begin = std::chrono::duration<double>(context.time - context.step).count();
                const double step  = std::chrono::duration<double>(context.step).count();
                advance(model, begin, step);
            },
            "oscillator dynamics");
        const auto observation = simulation.every(
            100ms, trick2::Phase::observation,
            [&](const trick2::StepContext& context)
            {
                const auto snapshot = registry.snapshot();
                if (snapshot.size() != 1 || snapshot[0].fields.size() != 3)
                {
                    throw std::logic_error("unexpected example schema");
                }
                const double time     = std::chrono::duration<double>(context.time).count();
                const double position = snapshot[0].fields[0].value;
                const double velocity = snapshot[0].fields[1].value;
                const double error    = std::hypot(position - std::cos(time), velocity + std::sin(time));
                if (!std::isfinite(error))
                {
                    throw std::logic_error("nonfinite oscillator state");
                }
                if (error > max_error)
                    max_error = error;
                ++observations;
                if (!verify)
                    std::cout << time << ',' << position << ',' << velocity << '\n';
            },
            "telemetry");
        (void)dynamics;
        (void)observation;

        // Two calls deliberately demonstrate continuation without restarting jobs.
        simulation.run_until(5s);
        simulation.run_until(10s);
        if (simulation.time() != 10s || observations != 100 || max_error > 1e-9)
        {
            std::cerr << "Oscillator verification failed: samples=" << observations << ", max error=" << max_error
                      << '\n';
            return 1;
        }
        if (verify)
            std::cout << "Oscillator verified: 100 samples, max error=" << max_error << '\n';
        return 0;
    }

} // namespace example
