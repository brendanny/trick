/*
PURPOSE: (Variable names resolved by the Memory Manager, staged into Snapshots.)

This is the adapter between the variable server core (trick/vs) and the
Memory Manager. It is part of libtrick. ICG and SWIG never parse it.

MemoryResolver looks a name up with ref_attributes() and owns the REF2
through RefPtr (ref_free plus free). Each ResolvedVar has a StagePlan,
made once from the REF2 and its ATTRIBUTES, that says how to copy its
value: where the bytes are, how many, and the FieldDesc the encoders read.

The plans follow the old VariableReference, with the accepted fixes:

  * A string is staged at its real length; the old 4096-byte stage buffer
    overflowed (Phase 0).
  * An enum is staged with its real size (Phase 0).
  * A char array reached through std::vector<T*> is staged whole; the old
    server staged its first character (Phase 0).
  * byteswap counts staged elements (Phase 0); the FieldDesc count is what
    was staged, never the declared length.
  * An unindexed pointer to numbers (double* p) stages the elements of the
    allocation it points to. The old server asked get_size() about the
    pointer's own address, so it staged nothing, or, for a pointer at the
    start of its allocation, read past the array (Phase 4 finding).
  * A reference through an STL container is looked up again before each
    copy, because the container may have moved its elements. The old server
    kept the first address.

Threads: resolve() and stage() may run on any thread, with the memory lock
held for reading (MemoryResolver::read_lock). A checkpoint load takes it for
writing and calls memory_replaced(); every ResolvedVar then resolves its
name again before its next copy.
*/

#ifndef TRICK_VS_ADAPTER_MEMORYRESOLVER_HH
#define TRICK_VS_ADAPTER_MEMORYRESOLVER_HH

#include "trick/vs/Expected.hh"
#include "trick/vs/FieldDesc.hh"
#include "trick/vs/Interfaces.hh"

#include "trick/reference.h"

#include <atomic>
#include <cstdint>
#include <memory>
#include <mutex>
#include <optional>
#include <shared_mutex>
#include <string>
#include <string_view>

namespace Trick
{
    namespace vs
    {
        namespace adapter
        {

            /** Frees a REF2 from ref_attributes(): its parts (ref_free), then the struct. */
            struct RefFree
            {
                    void operator()(REF2* ref) const noexcept;
            };

            using RefPtr = std::unique_ptr<REF2, RefFree>;

            /** ref_attributes() as a RefPtr. Null if the name does not resolve. Safe on any thread. */
            RefPtr resolve_ref(const std::string& name);

            /** How to stage one resolved name. Made by make_plan(). */
            struct StagePlan
            {
                    enum class Source
                    {
                        BadRef,       ///< not a variable: stage BAD_REF (retried, as the old server did)
                        NoValue,      ///< a whole struct or class: stage BAD_REF, never retried
                        Memory,       ///< `count` elements at the address
                        StdString,    ///< std::string: its characters and NUL
                        StdWString,   ///< std::wstring: its characters and NUL
                        CharPointer,  ///< char*: the C string it points to
                        WCharPointer, ///< wchar_t*: the wide C string it points to
                        Pointer       ///< T*: the elements of the allocation it points to
                    };

                    Source source = Source::BadRef;
                    /** The type, element size, text form, bitfield and units flag. count is set at stage time
                        for the string and pointer sources. */
                    FieldDesc desc = FieldDesc::bad_ref();
                    /** The address can change: follow the REF2's address path before each copy. */
                    bool follow_path = false;
                    /** Look the name up again before each copy (a path through an STL container). */
                    bool resolve_each_copy = false;
                    /** Why the plan is BadRef or NoValue, for the session log. */
                    std::string note;
            };

            /** The plan for a REF2 (null: BadRef). */
            StagePlan make_plan(const REF2* ref);

            /** The wire type of a TRICK_TYPE (the same numbers; TRICK_NUMBER_OF_TYPES is BAD_REF). */
            WireType wire_type(int trick_type) noexcept;

            class MemoryResolver : public Resolver
            {
                public:
                    MemoryResolver();
                    ~MemoryResolver() override;

                    std::unique_ptr<ResolvedVar> resolve(std::string_view name) override;

                    uint64_t memory_epoch() const override { return _epoch.load(std::memory_order_acquire); }

                    /** Hold while reading simulation memory (staging, resolving). */
                    std::shared_lock<std::shared_mutex> read_lock() const
                    {
                        return std::shared_lock<std::shared_mutex>(_memory);
                    }

                    /** Hold while simulation memory is replaced (checkpoint load). */
                    std::unique_lock<std::shared_mutex> write_lock() const
                    {
                        return std::unique_lock<std::shared_mutex>(_memory);
                    }

                    /** The lock itself, for a caller that must wait for it in its own way. */
                    std::shared_mutex& memory_mutex() const noexcept { return _memory; }

                    /** Call with write_lock() held, after simulation memory was replaced. */
                    void memory_replaced() noexcept { _epoch.fetch_add(1, std::memory_order_acq_rel); }

                private:
                    mutable std::shared_mutex _memory;
                    std::atomic<uint64_t> _epoch { 1 };
            };

            /**
             * A name resolved by a MemoryResolver. It keeps a pointer to its resolver,
             * which must outlive it.
             */
            class MemoryVar : public ResolvedVar
            {
                public:
                    MemoryVar(const MemoryResolver& resolver, std::string name);

                    const std::string& name() const override { return _name; }

                    bool resolved() const override { return _ref != nullptr; }

                    const std::string& base_units() const override { return _units; }

                    void stage(Snapshot& out, bool validate_address) override;

                    uint64_t epoch() const override { return _epoch; }

                    std::optional<int64_t> stl_size() const override;

                    const StagePlan& plan() const noexcept { return _plan; }

                    /** The last problem staging hit (a NULL pointer, a bad address), for the session log. Cleared on
                        read. */
                    std::string take_note() override { return std::move(_note); }

                private:
                    void resolve_again();

                    /** The address to copy from, or null for BAD_REF this time. */
                    const void* address(bool validate_address);

                    const MemoryResolver& _resolver;
                    std::string _name;
                    RefPtr _ref;
                    StagePlan _plan;
                    std::string _units;
                    uint64_t _epoch = 0;
                    std::string _note;
            };

        } // namespace adapter
    } // namespace vs
} // namespace Trick

#endif
