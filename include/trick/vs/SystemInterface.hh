/*
PURPOSE: (The system calls the variable server's network code makes.)

Every socket call in libtrick_var_server goes through a SystemInterface, so
tests can make a call fail (socket() returns EMFILE, send() returns EAGAIN)
without a real network. The default, system_interface(), calls the OS.

This replaces include/trick/SystemInterface.hh for the new code: it adds
poll, pipe and getpeername, drops select, and has no iostreams.
*/

#ifndef TRICK_VS_SYSTEMINTERFACE_HH
#define TRICK_VS_SYSTEMINTERFACE_HH

#include "trick/vs/Address.hh"

#include <cstddef>
#include <string>
#include <vector>

#include <netdb.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/types.h>

namespace Trick
{
    namespace vs
    {

        class SystemInterface
        {
            public:
                virtual ~SystemInterface();

                virtual int socket(int domain, int type, int protocol);
                virtual int setsockopt(int fd, int level, int name, const void* value, socklen_t length);
                virtual int bind(int fd, const sockaddr* address, socklen_t length);
                virtual int listen(int fd, int backlog);
                virtual int accept(int fd, sockaddr* address, socklen_t* length);
                virtual int getsockname(int fd, sockaddr* address, socklen_t* length);
                virtual int getpeername(int fd, sockaddr* address, socklen_t* length);
                virtual ssize_t recv(int fd, void* buffer, std::size_t length, int flags);
                virtual ssize_t recvfrom(int fd, void* buffer, std::size_t length, int flags, sockaddr* address,
                                         socklen_t* address_length);
                virtual ssize_t send(int fd, const void* buffer, std::size_t length, int flags);
                virtual ssize_t sendto(int fd, const void* buffer, std::size_t length, int flags,
                                       const sockaddr* address, socklen_t address_length);
                virtual ssize_t read(int fd, void* buffer, std::size_t length);
                virtual ssize_t write(int fd, const void* buffer, std::size_t length);
                virtual int poll(pollfd* fds, nfds_t count, int timeout_ms);
                virtual int pipe(int fds[2]);
                virtual int fcntl(int fd, int command, int argument);
                virtual int shutdown(int fd, int how);
                virtual int close(int fd);
                virtual int getaddrinfo(const char* host, const char* service, const addrinfo* hints, addrinfo** result);
                virtual void freeaddrinfo(addrinfo* list);
                /** The host name, as gethostname() gives it, or "" on failure. */
                virtual std::string hostname();
                /** The addresses of this host's interfaces (getifaddrs), ports 0. */
                virtual std::vector<Address> local_addresses();
        };

        /** The SystemInterface that calls the OS. It lives for the whole process. */
        SystemInterface& system_interface() noexcept;

        /** The text of an errno value, thread-safe. */
        std::string errno_text(int error);

    } // namespace vs
} // namespace Trick

#endif
