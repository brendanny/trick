#include "trick/vs/SystemInterface.hh"

#include <cerrno>
#include <cstring>

#include <fcntl.h>
#include <ifaddrs.h>
#include <unistd.h>

namespace Trick
{
    namespace vs
    {

        SystemInterface::~SystemInterface() = default;

        int SystemInterface::socket(int domain, int type, int protocol) { return ::socket(domain, type, protocol); }

        int SystemInterface::setsockopt(int fd, int level, int name, const void* value, socklen_t length)
        {
            return ::setsockopt(fd, level, name, value, length);
        }

        int SystemInterface::bind(int fd, const sockaddr* address, socklen_t length) { return ::bind(fd, address, length); }

        int SystemInterface::listen(int fd, int backlog) { return ::listen(fd, backlog); }

        int SystemInterface::accept(int fd, sockaddr* address, socklen_t* length) { return ::accept(fd, address, length); }

        int SystemInterface::getsockname(int fd, sockaddr* address, socklen_t* length)
        {
            return ::getsockname(fd, address, length);
        }

        int SystemInterface::getpeername(int fd, sockaddr* address, socklen_t* length)
        {
            return ::getpeername(fd, address, length);
        }

        ssize_t SystemInterface::recv(int fd, void* buffer, std::size_t length, int flags)
        {
            return ::recv(fd, buffer, length, flags);
        }

        ssize_t SystemInterface::recvfrom(int fd, void* buffer, std::size_t length, int flags, sockaddr* address,
                                          socklen_t* address_length)
        {
            return ::recvfrom(fd, buffer, length, flags, address, address_length);
        }

        ssize_t SystemInterface::send(int fd, const void* buffer, std::size_t length, int flags)
        {
            return ::send(fd, buffer, length, flags);
        }

        ssize_t SystemInterface::sendto(int fd, const void* buffer, std::size_t length, int flags,
                                        const sockaddr* address, socklen_t address_length)
        {
            return ::sendto(fd, buffer, length, flags, address, address_length);
        }

        ssize_t SystemInterface::read(int fd, void* buffer, std::size_t length) { return ::read(fd, buffer, length); }

        ssize_t SystemInterface::write(int fd, const void* buffer, std::size_t length)
        {
            return ::write(fd, buffer, length);
        }

        int SystemInterface::poll(pollfd* fds, nfds_t count, int timeout_ms) { return ::poll(fds, count, timeout_ms); }

        int SystemInterface::pipe(int fds[2]) { return ::pipe(fds); }

        int SystemInterface::fcntl(int fd, int command, int argument) { return ::fcntl(fd, command, argument); }

        int SystemInterface::shutdown(int fd, int how) { return ::shutdown(fd, how); }

        int SystemInterface::close(int fd) { return ::close(fd); }

        int SystemInterface::getaddrinfo(const char* host, const char* service, const addrinfo* hints,
                                         addrinfo** result)
        {
            return ::getaddrinfo(host, service, hints, result);
        }

        void SystemInterface::freeaddrinfo(addrinfo* list) { ::freeaddrinfo(list); }

        std::string SystemInterface::hostname()
        {
            char name[256] = {};
            if (::gethostname(name, sizeof name - 1) != 0)
                return std::string();
            return std::string(name);
        }

        std::vector<Address> SystemInterface::local_addresses()
        {
            std::vector<Address> out;
            ifaddrs* list = nullptr;
            if (::getifaddrs(&list) != 0)
                return out;
            for (ifaddrs* p = list; p != nullptr; p = p->ifa_next)
            {
                if (p->ifa_addr == nullptr)
                    continue;
                const socklen_t length = p->ifa_addr->sa_family == AF_INET6 ? sizeof(sockaddr_in6) : sizeof(sockaddr_in);
                Address a(p->ifa_addr, length);
                if (!a.empty())
                {
                    a.set_port(0);
                    out.push_back(a);
                }
            }
            ::freeifaddrs(list);
            return out;
        }

        SystemInterface& system_interface() noexcept
        {
            static SystemInterface real;
            return real;
        }

        namespace
        {
            // strerror_r has two forms: XSI returns int, GNU returns char*.
            [[maybe_unused]] inline const char* pick(int rc, const char* buffer) { return rc == 0 ? buffer : "unknown error"; }

            [[maybe_unused]] inline const char* pick(const char* text, const char*) { return text; }
        } // namespace

        std::string errno_text(int error)
        {
            char buffer[256] = {};
            return std::string(pick(::strerror_r(error, buffer, sizeof buffer), buffer));
        }

    } // namespace vs
} // namespace Trick
