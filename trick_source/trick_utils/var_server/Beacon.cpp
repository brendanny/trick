#include "trick/vs/Beacon.hh"

#include <cerrno>

namespace Trick
{
    namespace vs
    {

        const char* const beacon_groups[2] = { "239.3.14.15", "224.3.14.15" };

        std::string format_beacon(const BeaconInfo& info)
        {
            std::string version_text = info.version;
            const std::string& version = version_text;
            const std::size_t end = version_text.find_last_not_of(" \t\f\v\n\r");
            version_text.erase(end == std::string::npos ? 0 : end + 1);

            const std::string port = std::to_string(info.port);
            std::string out;
            out.reserve(256 + info.sim_dir.size() + info.input_file.size());
            for (const std::string* field : { &info.host, &port, &info.user })
            {
                out += *field;
                out += '\t';
            }
            out += std::to_string(info.pid);
            out += '\t';
            for (const std::string* field :
                 { &info.sim_dir, &info.executable, &info.input_file, &version, &info.user_tag, &port })
            {
                out += *field;
                out += '\t';
            }
            out += info.enabled ? '1' : '0';
            out += '\t';
            out += std::to_string(info.exec_mode);
            out += '\n';
            return out;
        }

        Expected<Beacon> Beacon::open(SystemInterface& sys, const std::vector<std::string>& groups, uint16_t port)
        {
            std::vector<Address> destinations;
            for (const std::string& g : groups)
            {
                auto a = Address::parse(g, port);
                if (!a || a->family() != AF_INET)
                    return Error { "beacon group [" + g + "] is not an IPv4 address" };
                destinations.push_back(*a);
            }
            Fd fd(sys.socket(AF_INET, SOCK_DGRAM, 0), sys);
            if (!fd)
                return system_error("socket", errno);
            if (auto r = set_cloexec(fd); !r)
                return r.error();
            const int one = 1;
            sys.setsockopt(fd.get(), SOL_SOCKET, SO_REUSEADDR, &one, sizeof one);
#ifdef SO_REUSEPORT
            sys.setsockopt(fd.get(), SOL_SOCKET, SO_REUSEPORT, &one, sizeof one);
#endif
            if (auto r = set_nonblocking(fd, true); !r)
                return r.error();
            return Beacon(std::move(fd), std::move(destinations));
        }

        Expected<void> Beacon::send(const std::string& message)
        {
            std::string errors;
            for (const Address& d : _destinations)
            {
                ssize_t n;
                do
                {
                    n = _fd.sys().sendto(_fd.get(), message.data(), message.size(), 0, d.data(), d.length());
                } while (n < 0 && errno == EINTR);
                if (n < 0)
                {
                    if (!errors.empty())
                        errors += '\n';
                    errors += "beacon to " + d.host() + ": " + errno_text(errno);
                }
            }
            if (!errors.empty())
                return Error { errors };
            return {};
        }

    } // namespace vs
} // namespace Trick
