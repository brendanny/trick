#include "trick/vs/TimeVar.hh"

namespace Trick
{
    namespace vs
    {

        const std::string& TimeVar::name() const
        {
            static const std::string n(variable_name);
            return n;
        }

        const std::string& TimeVar::base_units() const
        {
            static const std::string s("s");
            return s;
        }

        void TimeVar::stage(Snapshot& out, bool /*validate_address*/)
        {
            const double seconds = out.time_s;
            out.add(FieldDesc::scalar(WireType::Double, sizeof(double)), &seconds);
        }

    } // namespace vs
} // namespace Trick
