// Adapter: copy a session's values into a Snapshot (rewrite Phase 4).
// See include/trick/vs/adapter/Sampler.hh.

#include "trick/vs/adapter/Sampler.hh"

namespace Trick
{
    namespace vs
    {
        namespace adapter
        {

            template <class It> void Sampler::sample_range(Snapshot& out, It begin, It end, bool validate_address) const
            {
                const uint64_t sequence = out.sequence;
                out.clear();
                out.sequence = sequence + 1;

                const long long per = _clock.tic_value();
                out.time_tics       = _clock.time_tics();
                out.time_s          = per > 0 ? static_cast<double>(out.time_tics) / static_cast<double>(per) : 0.0;

                auto lock = _resolver.read_lock();
                for (It it = begin; it != end; ++it)
                    (*it)->stage(out, validate_address);
            }

            void Sampler::sample(Snapshot& out, const std::vector<ResolvedVar*>& vars, bool validate_address) const
            {
                sample_range(out, vars.begin(), vars.end(), validate_address);
            }

            void Sampler::sample(Snapshot& out, const std::vector<std::unique_ptr<ResolvedVar>>& vars,
                                 bool validate_address) const
            {
                sample_range(out, vars.begin(), vars.end(), validate_address);
            }

        } // namespace adapter
    } // namespace vs
} // namespace Trick
