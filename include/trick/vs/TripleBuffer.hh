/*
PURPOSE: (A single-producer, single-consumer triple buffer.)

The producer (the simulation main thread) fills back() and calls publish().
The consumer (the session runner) calls take() and reads front(). Neither
side waits for the other and no copy is skipped because the other side is
busy: publish() always succeeds, and take() gets the newest published slot.
A slot that was published but not taken is replaced by the next publish().

The three slots never move, so a slot keeps its capacity (a Snapshot reaches
its working size once and then needs no allocations).

Exactly one thread may call back() and publish(), and exactly one thread may
call take() and front(). The two threads may differ.
*/

#ifndef TRICK_VS_TRIPLEBUFFER_HH
#define TRICK_VS_TRIPLEBUFFER_HH

#include <array>
#include <atomic>
#include <cstdint>

namespace Trick
{
    namespace vs
    {

        template <class T> class TripleBuffer
        {
            public:
                TripleBuffer() = default;

                TripleBuffer(const TripleBuffer&)            = delete;
                TripleBuffer& operator=(const TripleBuffer&) = delete;

                /** Producer: the slot to fill. */
                T& back() noexcept { return _slots[_back]; }

                /** Producer: make back() the newest value. back() is then a different slot. */
                void publish() noexcept
                {
                    const uint8_t old = _middle.exchange(static_cast<uint8_t>(_back | fresh), std::memory_order_acq_rel);
                    _back             = static_cast<uint8_t>(old & index_mask);
                }

                /** Consumer: true if a value was published since the last take(); front() is then that value. */
                bool take() noexcept
                {
                    if ((_middle.load(std::memory_order_relaxed) & fresh) == 0)
                        return false;
                    const uint8_t old = _middle.exchange(_front, std::memory_order_acq_rel);
                    _front            = static_cast<uint8_t>(old & index_mask);
                    return true;
                }

                /** Consumer: the value from the last successful take(). */
                T& front() noexcept { return _slots[_front]; }

                const T& front() const noexcept { return _slots[_front]; }

                /** Either side: true if a published value waits for take(). Only a hint for the producer. */
                bool pending() const noexcept { return (_middle.load(std::memory_order_acquire) & fresh) != 0; }

            private:
                static constexpr uint8_t index_mask = 0x3;
                static constexpr uint8_t fresh      = 0x4;

                std::array<T, 3> _slots {};
                uint8_t _back  = 0; ///< producer only
                uint8_t _front = 1; ///< consumer only
                std::atomic<uint8_t> _middle { 2 };
        };

    } // namespace vs
} // namespace Trick

#endif
