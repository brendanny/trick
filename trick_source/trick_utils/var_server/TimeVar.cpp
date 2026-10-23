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
            const long long tics = _clock.time_tics();
            const long long per  = _clock.tic_value();
            const double seconds = per > 0 ? static_cast<double>(tics) / static_cast<double>(per) : 0.0;
            out.add(FieldDesc::scalar(WireType::Double, sizeof(double)), &seconds);
        }

    } // namespace vs
} // namespace Trick
