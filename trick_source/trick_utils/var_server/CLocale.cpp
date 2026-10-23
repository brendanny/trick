#include "trick/vs/CLocale.hh"

namespace Trick
{
    namespace vs
    {

        locale_t c_locale() noexcept
        {
            // newlocale() cannot fail for "C" in practice; if it does, (locale_t)0
            // makes uselocale() a query, so the thread keeps its locale.
            static const locale_t loc = newlocale(LC_ALL_MASK, "C", static_cast<locale_t>(0));
            return loc;
        }

    } // namespace vs
} // namespace Trick
