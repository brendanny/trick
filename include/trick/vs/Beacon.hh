/*
PURPOSE: (The multicast message that announces a running SIM.)

Every 2 s the server sends one datagram to 239.3.14.15 and to
224.3.14.15, port 9265 (the Java sim sniffer listens on the first, the
Python client on the second). The message has 12 tab-separated fields and
ends with a newline:

    host, port, user, pid, SIM directory, executable name, input file,
    Trick version, user tag, port again, enabled (0/1), executive mode

as the old VariableServerListenThread formatted it.
*/

#ifndef TRICK_VS_BEACON_HH
#define TRICK_VS_BEACON_HH

#include "trick/vs/Address.hh"
#include "trick/vs/Expected.hh"
#include "trick/vs/Fd.hh"

#include <cstdint>
#include <string>
#include <vector>

namespace Trick
{
    namespace vs
    {

        constexpr uint16_t beacon_port = 9265;

        /** The groups the beacon goes to, in the order the old server sent them. */
        extern const char* const beacon_groups[2];

        struct BeaconInfo
        {
                std::string host;
                uint16_t port = 0;
                std::string user;
                long pid = 0;
                std::string sim_dir;
                std::string executable;
                std::string input_file;
                std::string version; ///< trailing white space is removed, as the old server did
                std::string user_tag;
                bool enabled  = false;
                int exec_mode = 0;
        };

        /**
         * The beacon text. The old server wrote it into a 1024-byte buffer and so
         * cut long paths off, newline included; this one does not cut it.
         */
        std::string format_beacon(const BeaconInfo& info);

        class Beacon
        {
            public:
                /** A socket that sends to every group in `groups` at `port`. */
                static Expected<Beacon> open(SystemInterface& sys = system_interface(),
                                             const std::vector<std::string>& groups = { beacon_groups[0],
                                                                                        beacon_groups[1] },
                                             uint16_t port = beacon_port);

                Beacon(Beacon&&) noexcept            = default;
                Beacon& operator=(Beacon&&) noexcept = default;

                /** Send `message` to every group. Errors are returned, one line per group that failed. */
                Expected<void> send(const std::string& message);

                const std::vector<Address>& destinations() const noexcept { return _destinations; }

            private:
                Beacon(Fd fd, std::vector<Address> destinations)
                    : _fd(std::move(fd))
                    , _destinations(std::move(destinations))
                {
                }

                Fd _fd;
                std::vector<Address> _destinations;
        };

    } // namespace vs
} // namespace Trick

#endif
