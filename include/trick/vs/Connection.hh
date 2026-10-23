/*
PURPOSE: (One client's socket: TCP, UDP or multicast.)

A Connection is owned by one thread (the session runner). It never blocks:
read() takes what the socket has, and send() queues bytes that flush()
writes as the socket takes them. poll() on fd(), with POLLOUT while
wants_write() is true, tells the runner when to call them.

  * TCP: one client per accepted socket. A batch is the complete lines
    received so far (LineReader).
  * UDP: one session per socket (var_server_create_udp_socket). Each
    datagram is a batch: its bytes up to the last newline. Replies go to the
    sender of the last batch. The allowlist is checked against each
    datagram's sender; the old server checked an address it had not set.
  * Multicast: as UDP, but replies go to the group. The socket does not
    join the group and drops datagrams that it sent itself; the old server
    joined the group and could run its own replies as commands. When it is
    bound to loopback, commands come only from this host, and replies leave
    from a second socket that can reach the group.
*/

#ifndef TRICK_VS_CONNECTION_HH
#define TRICK_VS_CONNECTION_HH

#include "trick/vs/Address.hh"
#include "trick/vs/Expected.hh"
#include "trick/vs/Fd.hh"
#include "trick/vs/LineReader.hh"
#include "trick/vs/WriteQueue.hh"

#include <cstdint>
#include <functional>
#include <memory>
#include <string>
#include <string_view>
#include <vector>

namespace Trick
{
    namespace vs
    {

        enum class ConnectionKind
        {
            Tcp,
            Udp,
            Multicast
        };

        const char* connection_kind_name(ConnectionKind kind) noexcept;

        struct ReadResult
        {
                enum class Status
                {
                    Batch,   ///< `batch` holds one batch of command lines
                    Nothing, ///< no complete batch yet
                    Closed,  ///< the client closed the connection (TCP)
                    Error    ///< a socket error; `note` says which
                };

                Status status = Status::Nothing;
                /** A message for the session log, for any status (for example, discarded bytes). */
                std::string note;
        };

        struct FlushResult
        {
                enum class Status
                {
                    Done,    ///< the queue is empty
                    Pending, ///< the socket is full; poll for POLLOUT and call again
                    Error    ///< a socket error; the client is gone
                };

                Status status = Status::Done;
                std::string note;
                /** With Error: the client closed its end (EPIPE, ECONNRESET), a normal way to leave. */
                bool client_closed = false;
        };

        class Connection
        {
            public:
                virtual ~Connection();

                Connection(const Connection&)            = delete;
                Connection& operator=(const Connection&) = delete;

                virtual ConnectionKind kind() const noexcept = 0;

                int fd() const noexcept { return _fd.get(); }

                /** Read what the socket has, and give back at most one batch. Call until Nothing. */
                virtual ReadResult read(std::string& batch) = 0;

                /**
                 * Queue a message. False, and nothing queued, if the write queue is full;
                 * the session then drops the client (it is not reading).
                 */
                bool send(std::string_view message) { return _queue.push(message); }

                /** Write queued bytes until the queue is empty or the socket is full. */
                virtual FlushResult flush() = 0;

                bool wants_write() const noexcept { return !_queue.empty(); }

                const WriteQueue& queue() const noexcept { return _queue; }

                WriteQueue& queue() noexcept { return _queue; }

                /** The address replies go to (TCP: the client; UDP: the last sender; multicast: the group). */
                virtual Address peer() const = 0;

                /** The address the socket is bound to. */
                const Address& local() const noexcept { return _local; }

                /** Shut down and close the socket. Queued bytes are dropped. */
                void close() noexcept;

                bool is_open() const noexcept { return _fd.valid(); }

            protected:
                Connection(Fd fd, Address local, std::size_t queue_capacity)
                    : _fd(std::move(fd))
                    , _local(local)
                    , _queue(queue_capacity)
                {
                }

                SystemInterface& sys() const noexcept { return _fd.sys(); }

                Fd _fd;
                Address _local;
                WriteQueue _queue;
        };

        /** Options shared by the connection kinds. */
        struct ConnectionOptions
        {
                std::size_t queue_capacity = WriteQueue::default_capacity;
                std::size_t line_limit     = LineReader::default_limit;
        };

        class TcpConnection final : public Connection
        {
            public:
                /** Take an accepted, connected socket. Sets it non-blocking and close-on-exec. */
                static Expected<std::unique_ptr<TcpConnection>> adopt(Fd fd, const Address& peer,
                                                                      const ConnectionOptions& options = {});

                ConnectionKind kind() const noexcept override { return ConnectionKind::Tcp; }

                ReadResult read(std::string& batch) override;

                FlushResult flush() override;

                Address peer() const override { return _peer; }

                /** Bytes held that are not yet a complete line. */
                std::size_t pending_bytes() const noexcept { return _reader.pending(); }

            private:
                TcpConnection(Fd fd, Address local, Address peer, const ConnectionOptions& options)
                    : Connection(std::move(fd), local, options.queue_capacity)
                    , _peer(peer)
                    , _reader(options.line_limit)
                {
                }

                Address _peer;
                LineReader _reader;
                bool _eof = false;
        };

        /** Decides whether a datagram's sender may send commands (the allowlist). */
        using SenderFilter = std::function<bool(const Address& sender)>;

        class UdpConnection : public Connection
        {
            public:
                /**
                 * Bind a UDP socket for one session (var_server_create_udp_socket).
                 * `requested` follows resolve_bind_address() with SocketKind::Udp.
                 */
                static Expected<std::unique_ptr<UdpConnection>> open(SystemInterface& sys, std::string_view requested,
                                                                     uint16_t port, const ConnectionOptions& options = {});

                ConnectionKind kind() const noexcept override { return ConnectionKind::Udp; }

                ReadResult read(std::string& batch) override;

                FlushResult flush() override;

                Address peer() const override { return _reply_to; }

                /** The name the server reports for this socket. */
                const std::string& hostname() const noexcept { return _hostname; }

                /** Check each datagram's sender. Without a filter every sender is accepted. */
                void set_sender_filter(SenderFilter filter) { _filter = std::move(filter); }

            protected:
                UdpConnection(Fd fd, Address local, std::string hostname, const ConnectionOptions& options)
                    : Connection(std::move(fd), local, options.queue_capacity)
                    , _hostname(std::move(hostname))
                {
                }

                /** True if a datagram from `sender` is one this socket sent (multicast only). */
                virtual bool is_own(const Address& /*sender*/) const { return false; }

                /** The socket replies are sent from. */
                virtual int send_fd() const noexcept { return _fd.get(); }

                /** True if replies follow the sender of each batch (UDP), not a fixed address. */
                virtual bool reply_to_sender() const noexcept { return true; }

                Address _reply_to;
                std::string _hostname;
                SenderFilter _filter;
        };

        class MulticastConnection final : public UdpConnection
        {
            public:
                /**
                 * Bind a UDP socket that takes commands from clients and sends every
                 * reply to `group`:port (var_server_create_multicast_socket).
                 */
                static Expected<std::unique_ptr<MulticastConnection>> open(SystemInterface& sys, std::string_view group,
                                                                           std::string_view requested, uint16_t port,
                                                                           const ConnectionOptions& options = {});

                ConnectionKind kind() const noexcept override { return ConnectionKind::Multicast; }

                /** The address replies leave from: the bound socket, or the sender socket. */
                Address send_address() const;

            protected:
                bool is_own(const Address& sender) const override;

                bool reply_to_sender() const noexcept override { return false; }

                int send_fd() const noexcept override { return _sender ? _sender.get() : _fd.get(); }

            private:
                MulticastConnection(Fd fd, Fd sender, Address local, std::string hostname, Address group,
                                    std::vector<Address> own_hosts, const ConnectionOptions& options)
                    : UdpConnection(std::move(fd), local, std::move(hostname), options)
                    , _sender(std::move(sender))
                    , _own_hosts(std::move(own_hosts))
                {
                    _reply_to = group;
                }

                /**
                 * When the socket is bound to loopback (decision 12), replies leave from
                 * this second socket, bound to no address: a loopback interface usually
                 * has no multicast, so the bound socket could not reach the group.
                 */
                Fd _sender;
                std::vector<Address> _own_hosts;
        };

    } // namespace vs
} // namespace Trick

#endif
