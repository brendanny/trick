/*
PURPOSE: (The listener thread's work: accept clients and send the beacon.)

ListenLoop polls its listen sockets and a wake pipe. For each client that
connects it asks the owner, through a ListenPolicy, whether connections are
open and whether the client's address is allowed, and hands each accepted
client to the owner as a TcpConnection. Every beacon period it sends the
beacon. It never blocks on a client: the old listener waited for each new
session thread to accept its client.

As in the old server:
  * When the server is disabled or refuses connections, a client is
    accepted and closed at once, so it is not left waiting and the listen
    backlog does not fill.
  * A client that the allowlist refuses is closed, with an
    "ILLEGAL IP CONNECTION ATTEMPTED" message.
*/

#ifndef TRICK_VS_LISTENLOOP_HH
#define TRICK_VS_LISTENLOOP_HH

#include "trick/vs/Beacon.hh"
#include "trick/vs/Connection.hh"
#include "trick/vs/Listener.hh"
#include "trick/vs/Poller.hh"

#include <atomic>
#include <chrono>
#include <memory>
#include <optional>
#include <string>
#include <vector>

namespace Trick
{
    namespace vs
    {

        /** What ListenLoop asks its owner. Called on the listener thread. */
        class ListenPolicy
        {
            public:
                virtual ~ListenPolicy();

                /** True if new clients may connect (the server is enabled and allows connections). */
                virtual bool accepting() = 0;

                /** True if this client's address may connect (the allowlist, or its bypass). */
                virtual bool allowed(const Address& client) = 0;

                /** Take a new client. */
                virtual void connected(std::unique_ptr<TcpConnection> connection, const Listener& listener) = 0;

                /** The beacon text, or empty to send none now. */
                virtual std::string beacon_message(const Listener& listener) = 0;

                /** A message for the SIM's log. `error` is true for an error, false for information. */
                virtual void log(const std::string& message, bool error) = 0;
        };

        class ListenLoop
        {
            public:
                using Clock = std::chrono::steady_clock;

                static constexpr std::chrono::milliseconds default_beacon_period { 2000 };

                /**
                 * `beacon` may be empty: no beacon is sent. The beacon goes out for the
                 * first listener only, as each old listener thread sent its own.
                 */
                static Expected<std::unique_ptr<ListenLoop>> create(ListenPolicy& policy, std::optional<Beacon> beacon,
                                                                    ConnectionOptions options = {},
                                                                    SystemInterface& sys = system_interface());

                /** Add a listener. Only before run(), or from the thread that runs the loop. */
                void add(Listener listener) { _listeners.push_back(std::move(listener)); }

                const std::vector<Listener>& listeners() const noexcept { return _listeners; }

                void set_beacon_period(std::chrono::milliseconds period) noexcept { _beacon_period = period; }

                /**
                 * One round: wait for clients, at most until the next beacon or
                 * `max_wait`, accept them, and send the beacon when it is due.
                 */
                void run_once(std::chrono::milliseconds max_wait = std::chrono::milliseconds(1000));

                /** Run rounds until stop(). */
                void run();

                /** Make run() return. Safe from any thread. */
                void stop() noexcept;

                bool stopping() const noexcept { return _stop.load(std::memory_order_acquire); }

                /** Wake the loop, for example after the beacon text changed. Safe from any thread. */
                void wake() const noexcept { _poller.wake(); }

            private:
                ListenLoop(ListenPolicy& policy, std::optional<Beacon> beacon, ConnectionOptions options, Poller poller)
                    : _policy(policy)
                    , _beacon(std::move(beacon))
                    , _options(options)
                    , _poller(std::move(poller))
                {
                }

                void accept_all(Listener& listener);

                void send_beacon();

                ListenPolicy& _policy;
                std::optional<Beacon> _beacon;
                ConnectionOptions _options;
                Poller _poller;
                std::vector<Listener> _listeners;
                std::vector<pollfd> _items;
                std::chrono::milliseconds _beacon_period = default_beacon_period;
                std::optional<Clock::time_point> _next_beacon;
                std::string _last_beacon_error;
                std::atomic<bool> _stop { false };
        };

    } // namespace vs
} // namespace Trick

#endif
