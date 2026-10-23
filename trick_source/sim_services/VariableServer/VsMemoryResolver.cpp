// Adapter: variable names resolved by the Memory Manager (rewrite Phase 4).
// See include/trick/vs/adapter/MemoryResolver.hh.

#include "trick/vs/adapter/MemoryResolver.hh"

#include "trick/attributes.h"
#include "trick/memorymanager_c_intf.h"
#include "trick/reference.h"

#include <cstdlib>
#include <cstring>
#include <cwchar>
#include <string>

namespace Trick
{
    namespace vs
    {
        namespace adapter
        {

            void RefFree::operator()(REF2* ref) const noexcept
            {
                if (ref != nullptr)
                {
                    ref_free(ref);
                    std::free(ref);
                }
            }

            std::mutex& ref_attributes_lock() noexcept
            {
                static std::mutex m;
                return m;
            }

            RefPtr resolve_ref(const std::string& name)
            {
                // ref_attributes() writes the parser's global debug flag on every call
                // (MemoryManager_ref_attributes.cpp), so two calls at once race (TSan,
                // Phase 4). The old server called it from every session thread.
                std::lock_guard<std::mutex> guard(ref_attributes_lock());
                return RefPtr(ref_attributes(name.c_str()));
            }

            WireType wire_type(int trick_type) noexcept
            {
                if (trick_type >= static_cast<int>(TRICK_VOID) && trick_type < static_cast<int>(TRICK_NUMBER_OF_TYPES))
                    return static_cast<WireType>(trick_type);
                return WireType::BadRef;
            }

            namespace
            {
                /** The size of one element of an STL container of `type` (ReferenceUtils' rule). */
                uint32_t stl_element_size(TRICK_TYPE type) noexcept
                {
                    switch (type)
                    {
                        case TRICK_CHARACTER:
                        case TRICK_UNSIGNED_CHARACTER:
                        case TRICK_BOOLEAN:
                            return 1;
                        case TRICK_SHORT:
                        case TRICK_UNSIGNED_SHORT:
                            return sizeof(short);
                        case TRICK_INTEGER:
                        case TRICK_UNSIGNED_INTEGER:
                        case TRICK_ENUMERATED:
                            return sizeof(int);
                        case TRICK_LONG:
                        case TRICK_UNSIGNED_LONG:
                            return sizeof(long);
                        case TRICK_LONG_LONG:
                        case TRICK_UNSIGNED_LONG_LONG:
                            return sizeof(long long);
                        case TRICK_FLOAT:
                            return sizeof(float);
                        case TRICK_DOUBLE:
                            return sizeof(double);
                        case TRICK_STRING:
                        case TRICK_WSTRING:
                        case TRICK_STRUCTURED:
                            return sizeof(void*);
                        default:
                            return 0;
                    }
                }

                /** The reference names an element of an STL container itself (vec[0]). */
                bool is_stl_element(const REF2& ref) noexcept
                {
                    if (ref.attr->type != TRICK_STL || ref.reference == nullptr)
                        return false;
                    const std::size_t n = std::strlen(ref.reference);
                    return n > 0 && ref.reference[n - 1] == ']';
                }

                StagePlan bad(StagePlan::Source source, std::string note)
                {
                    StagePlan p;
                    p.source = source;
                    p.desc   = FieldDesc::bad_ref();
                    p.note   = std::move(note);
                    return p;
                }
            } // namespace

            StagePlan make_plan(const REF2* ref)
            {
                if (ref == nullptr)
                    return bad(StagePlan::Source::BadRef, "the Memory Manager does not know this name");
                if (ref->attr == nullptr)
                    return bad(StagePlan::Source::BadRef, "the reference has no ATTRIBUTES");
                const ATTRIBUTES& a = *ref->attr;
                const std::string name = ref->reference ? ref->reference : "";

                if (a.type == TRICK_STRUCTURED)
                    return bad(StagePlan::Source::NoValue,
                               "var_add cannot add \"" + name + "\" because it is a composite variable");

                StagePlan p;
                const bool stl_element  = is_stl_element(*ref);
                const bool through_stl  = stl_element || ref->stl_present == 1;
                p.resolve_each_copy     = through_stl;
                p.follow_path           = ref->pointer_present == 1 && !through_stl;
                const bool dashdash     = (a.mods & TRICK_MODS_UNITSDASHDASH) != 0;

                auto finish = [&](StagePlan plan) {
                    plan.desc.units_dashdash = dashdash;
                    if (const char* why = validate(plan.desc))
                    {
                        // The pointer and string sources set the count when they stage.
                        const bool count_later = plan.source != StagePlan::Source::Memory;
                        if (!count_later)
                            return bad(StagePlan::Source::BadRef, "cannot stage \"" + name + "\": " + why);
                    }
                    return plan;
                };

                if (stl_element)
                {
                    const TRICK_TYPE t = a.stl_elem_type;
                    if (t == TRICK_STRING)
                    {
                        p.source = StagePlan::Source::StdString;
                        p.desc   = FieldDesc::narrow_string(0);
                    }
                    else if (t == TRICK_WSTRING)
                    {
                        p.source = StagePlan::Source::StdWString;
                        p.desc   = FieldDesc::wide_string(0);
                    }
                    else
                    {
                        p.source = StagePlan::Source::Memory;
                        p.desc   = FieldDesc::scalar(wire_type(t), stl_element_size(t));
                    }
                    return finish(p);
                }

                const TRICK_TYPE t   = a.type;
                const int remaining  = a.num_index - ref->num_index; // dimensions not indexed
                const uint32_t esize = static_cast<uint32_t>(a.size);

                if (t == TRICK_STRING || t == TRICK_WSTRING)
                {
                    // A std::string or std::wstring (the first, for an array of them, as before).
                    p.source = t == TRICK_STRING ? StagePlan::Source::StdString : StagePlan::Source::StdWString;
                    p.desc   = t == TRICK_STRING ? FieldDesc::narrow_string(0) : FieldDesc::wide_string(0);
                    return finish(p);
                }

                if (remaining <= 0)
                {
                    p.source = StagePlan::Source::Memory;
                    p.desc   = FieldDesc::scalar(wire_type(t), esize);
                    if (t == TRICK_BITFIELD || t == TRICK_UNSIGNED_BITFIELD)
                    {
                        p.desc.bitfield.start = static_cast<uint16_t>(a.index[0].start);
                        p.desc.bitfield.width = static_cast<uint16_t>(a.index[0].size);
                    }
                    return finish(p);
                }

                const bool constrained = a.index[a.num_index - 1].size != 0;
                if (constrained)
                {
                    uint64_t count = 1;
                    for (int i = ref->num_index; i < a.num_index; ++i)
                        count *= static_cast<uint64_t>(a.index[i].size);
                    p.source = StagePlan::Source::Memory;
                    p.desc   = FieldDesc::array(wire_type(t), esize, static_cast<uint32_t>(count));
                    if (t == TRICK_CHARACTER || t == TRICK_UNSIGNED_CHARACTER)
                        p.desc.text = Text::Narrow;
                    else if (t == TRICK_WCHAR)
                        p.desc.text = Text::Wide;
                    return finish(p);
                }

                // The last dimension is a pointer.
                if (remaining > 1)
                    return bad(StagePlan::Source::BadRef,
                               "var_add(" + name + ") asks for more than one dimension of a dynamic array; its data is not "
                                                   "contiguous");
                p.follow_path = ref->pointer_present == 1 && !through_stl;
                if (t == TRICK_CHARACTER)
                {
                    p.source = StagePlan::Source::CharPointer;
                    p.desc   = FieldDesc::narrow_string(0);
                }
                else if (t == TRICK_WCHAR)
                {
                    p.source = StagePlan::Source::WCharPointer;
                    p.desc   = FieldDesc::wide_string(0);
                }
                else
                {
                    p.source = StagePlan::Source::Pointer;
                    p.desc   = FieldDesc::array(wire_type(t), esize, 0);
                }
                return finish(p);
            }

            // --------------------------------------------------------------
            // MemoryResolver
            // --------------------------------------------------------------

            MemoryResolver::MemoryResolver()  = default;
            MemoryResolver::~MemoryResolver() = default;

            std::unique_ptr<ResolvedVar> MemoryResolver::resolve(std::string_view name)
            {
                return std::make_unique<MemoryVar>(*this, std::string(name));
            }

            // --------------------------------------------------------------
            // MemoryVar
            // --------------------------------------------------------------

            MemoryVar::MemoryVar(const MemoryResolver& resolver, std::string name)
                : _resolver(resolver)
                , _name(std::move(name))
            {
                resolve_again();
            }

            void MemoryVar::resolve_again()
            {
                _ref   = resolve_ref(_name);
                _plan  = make_plan(_ref.get());
                _units = (_ref && _ref->attr && _ref->attr->units) ? _ref->attr->units : "";
                _epoch = _resolver.memory_epoch();
            }

            std::optional<int64_t> MemoryVar::stl_size() const
            {
                if (!_ref || _ref->attr == nullptr || _ref->attr->type != TRICK_STL || _ref->attr->get_stl_size == nullptr
                    || is_stl_element(*_ref) || _ref->address == nullptr)
                    return std::nullopt;
                return static_cast<int64_t>(_ref->attr->get_stl_size(_ref->address));
            }

            const void* MemoryVar::address(bool validate_address)
            {
                void* a = _ref->address;
                if (_plan.follow_path)
                {
                    if (validate_address)
                    {
                        // Follow the path one step at a time, and check each pointer before
                        // it is read and each address it gives.
                        a = nullptr;
                        DLLPOS pos = DLL_GetHeadPosition(_ref->address_path);
                        while (pos != nullptr)
                        {
                            const ADDRESS_NODE* node = static_cast<ADDRESS_NODE*>(DLL_GetNext(&pos, _ref->address_path));
                            switch (node->operator_)
                            {
                                case AO_ADDRESS:
                                    a = node->operand.address;
                                    break;
                                case AO_OFFSET:
                                    a = static_cast<char*>(a) + node->operand.offset;
                                    break;
                                case AO_DEREFERENCE:
                                    if (get_alloc_info_of(a) == nullptr)
                                    {
                                        _note = "\"" + _name + "\": a pointer on its path is not in Memory Manager memory";
                                        return nullptr;
                                    }
                                    a = *static_cast<char**>(a);
                                    break;
                            }
                            if (a == nullptr)
                            {
                                _note = "\"" + _name + "\": a pointer on its path is NULL";
                                return nullptr;
                            }
                        }
                        if (a != nullptr && get_alloc_info_of(a) == nullptr)
                        {
                            _note = "\"" + _name + "\" points to memory the Memory Manager does not know";
                            return nullptr;
                        }
                    }
                    else
                    {
                        a = follow_address_path(_ref.get());
                    }
                    if (a == nullptr)
                    {
                        _note = "\"" + _name + "\": a pointer on its path is NULL";
                        return nullptr;
                    }
                }
                return a;
            }

            void MemoryVar::stage(Snapshot& out, bool validate_address)
            {
                const bool retry = _plan.source == StagePlan::Source::BadRef; // as the old server, every copy
                if (_epoch != _resolver.memory_epoch() || _plan.resolve_each_copy || retry)
                    resolve_again();

                if (_plan.source == StagePlan::Source::BadRef || _plan.source == StagePlan::Source::NoValue)
                {
                    out.add_bad_ref();
                    return;
                }

                const void* a = address(validate_address);
                if (a == nullptr)
                {
                    out.add_bad_ref();
                    return;
                }

                FieldDesc d = _plan.desc;
                switch (_plan.source)
                {
                    case StagePlan::Source::Memory:
                        out.add(d, a);
                        return;

                    case StagePlan::Source::StdString:
                    {
                        // The old server copied strlen + 1 bytes into a 4096-byte buffer.
                        const char* text = static_cast<const std::string*>(a)->c_str();
                        d       = FieldDesc::narrow_string(static_cast<uint32_t>(std::strlen(text)));
                        d.units_dashdash = _plan.desc.units_dashdash;
                        out.add(d, text);
                        return;
                    }

                    case StagePlan::Source::StdWString:
                    {
                        const wchar_t* text = static_cast<const std::wstring*>(a)->c_str();
                        d       = FieldDesc::wide_string(static_cast<uint32_t>(std::wcslen(text)));
                        d.units_dashdash = _plan.desc.units_dashdash;
                        out.add(d, text);
                        return;
                    }

                    case StagePlan::Source::CharPointer:
                    {
                        const char* text = *static_cast<char* const*>(a);
                        if (text == nullptr)
                        {
                            d.count = 0; // a NULL char* prints as an empty field
                            out.add(d, nullptr);
                            return;
                        }
                        d       = FieldDesc::narrow_string(static_cast<uint32_t>(std::strlen(text)));
                        d.units_dashdash = _plan.desc.units_dashdash;
                        out.add(d, text);
                        return;
                    }

                    case StagePlan::Source::WCharPointer:
                    {
                        const wchar_t* text = *static_cast<wchar_t* const*>(a);
                        if (text == nullptr)
                        {
                            d.count = 0;
                            out.add(d, nullptr);
                            return;
                        }
                        d       = FieldDesc::wide_string(static_cast<uint32_t>(std::wcslen(text)));
                        d.units_dashdash = _plan.desc.units_dashdash;
                        out.add(d, text);
                        return;
                    }

                    case StagePlan::Source::Pointer:
                    {
                        // Phase 4 fix: the elements of the allocation the pointer points to,
                        // from the pointer to the end of that allocation.
                        void* target = *static_cast<void* const*>(a);
                        const int n  = target != nullptr ? get_truncated_size(target) : 0;
                        d.count      = n > 0 ? static_cast<uint32_t>(n) : 0;
                        out.add(d, d.count > 0 ? target : nullptr);
                        return;
                    }

                    case StagePlan::Source::BadRef:
                    case StagePlan::Source::NoValue:
                        break;
                }
                out.add_bad_ref();
            }

        } // namespace adapter
    } // namespace vs
} // namespace Trick
