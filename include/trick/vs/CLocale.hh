/*
PURPOSE: (Use the C locale on this thread while an object lives.)

The wire format and the parser need '.' as the decimal point, whatever
locale the simulation sets. uselocale() changes only the calling thread,
so it is safe in a session thread.
*/

#ifndef TRICK_VS_CLOCALE_HH
#define TRICK_VS_CLOCALE_HH

#include <clocale>
#include <locale.h>
#if defined(__APPLE__)
#include <xlocale.h>
#endif

namespace Trick
{
    namespace vs
    {

        /** The "C" locale object, made once for the process. */
        locale_t c_locale() noexcept;

        class ScopedCLocale
        {
            public:
                ScopedCLocale() noexcept
                    : _previous(uselocale(c_locale()))
                {
                }

                ~ScopedCLocale() { uselocale(_previous); }

                ScopedCLocale(const ScopedCLocale&)            = delete;
                ScopedCLocale& operator=(const ScopedCLocale&) = delete;

            private:
                locale_t _previous;
        };

    } // namespace vs
} // namespace Trick

#endif
