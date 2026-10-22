/*
PURPOSE: (A value or an error message, for the variable server core.)
*/

#ifndef TRICK_VS_EXPECTED_HH
#define TRICK_VS_EXPECTED_HH

#include <string>
#include <utility>
#include <variant>

namespace Trick
{
    namespace vs
    {

        /** An error message. The variable server writes it to the session log. */
        struct Error
        {
                std::string message;
        };

        /**
         * A value of type T, or an Error. C++17 has no std::expected; this is the
         * part of it that the variable server uses.
         */
        template <class T> class Expected
        {
            public:
                Expected(T value)
                    : _v(std::in_place_index<0>, std::move(value))
                {
                }

                Expected(Error error)
                    : _v(std::in_place_index<1>, std::move(error))
                {
                }

                bool has_value() const noexcept { return _v.index() == 0; }

                explicit operator bool() const noexcept { return has_value(); }

                /** Precondition: has_value(). Otherwise throws std::bad_variant_access. */
                T& value() & { return std::get<0>(_v); }

                const T& value() const& { return std::get<0>(_v); }

                T&& value() && { return std::get<0>(std::move(_v)); }

                /** Precondition: !has_value(). Otherwise throws std::bad_variant_access. */
                const Error& error() const { return std::get<1>(_v); }

            private:
                std::variant<T, Error> _v;
        };

        /** Expected<void>: success, or an Error. */
        template <> class Expected<void>
        {
            public:
                Expected() = default;

                Expected(Error error)
                    : _error(std::move(error))
                    , _ok(false)
                {
                }

                bool has_value() const noexcept { return _ok; }

                explicit operator bool() const noexcept { return _ok; }

                const Error& error() const { return _error; }

            private:
                Error _error;
                bool _ok = true;
        };

    } // namespace vs
} // namespace Trick

#endif
