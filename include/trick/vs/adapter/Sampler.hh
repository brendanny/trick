/*
PURPOSE: (Copy a session's values from simulation memory into a Snapshot.)

The Sampler holds the Memory Manager read lock while it stages, so a
checkpoint load cannot replace memory in the middle of a copy. It runs on
the simulation main thread (scheduled and top-of-frame copies) or on the
session runner (asynchronous copies).
*/

#ifndef TRICK_VS_ADAPTER_SAMPLER_HH
#define TRICK_VS_ADAPTER_SAMPLER_HH

#include "trick/vs/Interfaces.hh"
#include "trick/vs/Snapshot.hh"
#include "trick/vs/adapter/MemoryResolver.hh"

#include <cstddef>
#include <memory>
#include <vector>

namespace Trick
{
    namespace vs
    {
        namespace adapter
        {

            class Sampler
            {
                public:
                    /** `resolver` and `clock` must outlive the Sampler. */
                    Sampler(const MemoryResolver& resolver, const Clock& clock) noexcept
                        : _resolver(resolver)
                        , _clock(clock)
                    {
                    }

                    /**
                     * Clear `out`, then stage each variable, in order: one value each.
                     * Sets the snapshot's time and increases its sequence number.
                     */
                    void sample(Snapshot& out, const std::vector<ResolvedVar*>& vars, bool validate_address) const;

                    void sample(Snapshot& out, const std::vector<std::unique_ptr<ResolvedVar>>& vars,
                                bool validate_address) const;

                private:
                    template <class It> void sample_range(Snapshot& out, It begin, It end, bool validate_address) const;

                    const MemoryResolver& _resolver;
                    const Clock& _clock;
            };

        } // namespace adapter
    } // namespace vs
} // namespace Trick

#endif
