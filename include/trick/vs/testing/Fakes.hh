/*
PURPOSE: (Test fakes for the variable server interfaces.)

Header only. Tests of the core library and of the session logic use these
in place of the Memory Manager, the executive, UDUNITS and Python.
*/

#ifndef TRICK_VS_TESTING_FAKES_HH
#define TRICK_VS_TESTING_FAKES_HH

#include "trick/vs/Interfaces.hh"

#include <cstring>
#include <map>
#include <memory>
#include <optional>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace Trick
{
    namespace vs
    {
        namespace testing
        {

            class FakeClock : public Clock
            {
                public:
                    long long time            = 0;
                    long long tics_per_second = 1000000;
                    long long frame           = 0;
                    long long freeze_time     = 0;
                    long long freeze_frame    = 0;
                    bool is_real_time         = false;
                    int mode                  = 1;

                    long long time_tics() const override { return time; }

                    long long tic_value() const override { return tics_per_second; }

                    long long frame_count() const override { return frame; }

                    long long freeze_time_tics() const override { return freeze_time; }

                    long long freeze_frame_count() const override { return freeze_frame; }

                    bool real_time() const override { return is_real_time; }

                    int exec_mode() const override { return mode; }
            };

            /** A simulation variable held by FakeResolver. Tests change `bytes` to change its value. */
            struct FakeVariable
            {
                    FieldDesc desc;
                    std::vector<unsigned char> bytes;
                    std::string units;
                    bool valid_address = true;
                    std::optional<int64_t> stl_size;
            };

            class FakeResolvedVar : public ResolvedVar
            {
                public:
                    FakeResolvedVar(std::string name, std::shared_ptr<FakeVariable> var, uint64_t epoch)
                        : _name(std::move(name))
                        , _var(std::move(var))
                        , _epoch(epoch)
                    {
                    }

                    const std::string& name() const override { return _name; }

                    bool resolved() const override { return _var != nullptr; }

                    const std::string& base_units() const override
                    {
                        static const std::string none;
                        return _var ? _var->units : none;
                    }

                    void stage(Snapshot& out, bool validate_address) override
                    {
                        ++stage_calls;
                        last_validate_address = validate_address;
                        if (!_var || (validate_address && !_var->valid_address))
                        {
                            out.add_bad_ref();
                            return;
                        }
                        out.add(_var->desc, _var->bytes.data());
                    }

                    uint64_t epoch() const override { return _epoch; }

                    std::optional<int64_t> stl_size() const override { return _var ? _var->stl_size : std::nullopt; }

                    int stage_calls            = 0;
                    bool last_validate_address = false;

                private:
                    std::string _name;
                    std::shared_ptr<FakeVariable> _var;
                    uint64_t _epoch;
            };

            class FakeResolver : public Resolver
            {
                public:
                    /** Add or replace a variable. `data` must hold desc.byte_size() bytes. */
                    std::shared_ptr<FakeVariable> set(const std::string& name, const FieldDesc& desc, const void* data,
                                                      std::string units = "--")
                    {
                        auto var      = std::make_shared<FakeVariable>();
                        var->desc     = desc;
                        var->units    = std::move(units);
                        const auto* p = static_cast<const unsigned char*>(data);
                        var->bytes.assign(p, p + desc.byte_size());
                        _vars[name] = var;
                        return var;
                    }

                    template <class T>
                    std::shared_ptr<FakeVariable> set_scalar(const std::string& name, WireType type, T value,
                                                             std::string units = "--")
                    {
                        return set(name, FieldDesc::scalar(type, sizeof(T)), &value, std::move(units));
                    }

                    void remove(const std::string& name) { _vars.erase(name); }

                    /** The variable with this exact name, or null. */
                    std::shared_ptr<FakeVariable> find(const std::string& name) const
                    {
                        auto it = _vars.find(name);
                        return it == _vars.end() ? nullptr : it->second;
                    }

                    std::unique_ptr<ResolvedVar> resolve(std::string_view name) override
                    {
                        ++resolve_calls;
                        auto it  = _vars.find(std::string(name));
                        auto var = it == _vars.end() ? nullptr : it->second;
                        return std::make_unique<FakeResolvedVar>(std::string(name), var, epoch);
                    }

                    uint64_t memory_epoch() const override { return epoch; }

                    uint64_t epoch    = 1;
                    int resolve_calls = 0;

                private:
                    std::map<std::string, std::shared_ptr<FakeVariable>> _vars;
            };

            class FakeConversion : public Conversion
            {
                public:
                    FakeConversion(double scale, double offset)
                        : _scale(scale)
                        , _offset(offset)
                    {
                    }

                    double apply(double value) const override { return value * _scale + _offset; }

                private:
                    double _scale;
                    double _offset;
            };

            /** Knows only the conversions and names that a test adds. */
            class FakeUnitConverter : public UnitConverter
            {
                public:
                    void add(std::string from, std::string to, double scale, double offset = 0.0)
                    {
                        _table[{ std::move(from), std::move(to) }] = { scale, offset };
                    }

                    void add_name(std::string name, std::string canonical_name)
                    {
                        _names[std::move(name)] = std::move(canonical_name);
                    }

                    Expected<std::unique_ptr<Conversion>> converter(std::string_view from, std::string_view to) override
                    {
                        if (from == to)
                        {
                            return std::unique_ptr<Conversion>();
                        }
                        auto it = _table.find({ std::string(from), std::string(to) });
                        if (it == _table.end())
                        {
                            return Error { "cannot convert units from [" + std::string(from) + "] to ["
                                           + std::string(to) + "]" };
                        }
                        return std::unique_ptr<Conversion>(new FakeConversion(it->second.first, it->second.second));
                    }

                    Expected<std::string> canonical(std::string_view units) override
                    {
                        auto it = _names.find(std::string(units));
                        if (it == _names.end())
                        {
                            return Error { "unknown units [" + std::string(units) + "]" };
                        }
                        return it->second;
                    }

                private:
                    std::map<std::pair<std::string, std::string>, std::pair<double, double>> _table;
                    std::map<std::string, std::string> _names;
            };

            /** Records each line. Set `fail_with` to make run() fail. */
            class FakeCommandFallback : public CommandFallback
            {
                public:
                    Expected<void> run(std::string_view text) override
                    {
                        lines.emplace_back(text);
                        if (!fail_with.empty())
                        {
                            return Error { fail_with };
                        }
                        return { };
                    }

                    std::vector<std::string> lines;
                    std::string fail_with;
            };

        } // namespace testing
    } // namespace vs
} // namespace Trick

#endif
