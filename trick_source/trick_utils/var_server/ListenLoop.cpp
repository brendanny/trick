#include "trick/vs/ListenLoop.hh"

#include <algorithm>

namespace Trick
{
    namespace vs
    {

        ListenPolicy::~ListenPolicy() = default;

        constexpr std::chrono::milliseconds ListenLoop::default_beacon_period;

        Expected<std::unique_ptr<ListenLoop>> ListenLoop::create(ListenPolicy& policy, std::optional<Beacon> beacon,
                                                                 ConnectionOptions options, SystemInterface& sys)
        {
            auto poller = Poller::create(sys);
            if (!poller)
                return poller.error();
            return std::unique_ptr<ListenLoop>(
                new ListenLoop(policy, std::move(beacon), options, std::move(poller.value())));
        }

        void ListenLoop::stop() noexcept
        {
            _stop.store(true, std::memory_order_release);
            _poller.wake();
        }

        void ListenLoop::run()
        {
            while (!stopping())
                run_once();
        }

        void ListenLoop::run_once(std::chrono::milliseconds max_wait)
        {
            const Clock::time_point now = Clock::now();
            if (_beacon && !_next_beacon)
                _next_beacon = now; // the first beacon goes out at once

            auto wait = max_wait;
            if (_beacon && _next_beacon)
                wait = std::min(wait, std::max(std::chrono::milliseconds(0),
                                               std::chrono::duration_cast<std::chrono::milliseconds>(*_next_beacon - now)));

            _items.clear();
            for (const Listener& l : _listeners)
                if (l.is_open())
                    _items.push_back(pollfd { l.fd(), POLLIN, 0 });

            auto r = _poller.wait(_items, static_cast<int>(wait.count()));
            if (!r)
                _policy.log("variable server listener: " + r.error().message, true);

            if (stopping())
                return;

            std::size_t item = 0;
            for (Listener& l : _listeners)
            {
                if (!l.is_open())
                    continue;
                if (_items[item++].revents & (POLLIN | POLLERR | POLLHUP))
                    accept_all(l);
            }

            if (_beacon && _next_beacon && Clock::now() >= *_next_beacon)
            {
                send_beacon();
                *_next_beacon += _beacon_period;
                // After a long stall, do not send a burst to catch up.
                if (*_next_beacon < Clock::now())
                    _next_beacon = Clock::now() + _beacon_period;
            }
        }

        void ListenLoop::accept_all(Listener& listener)
        {
            // Accept everything that is waiting, but not forever.
            for (int i = 0; i < 64; ++i)
            {
                auto a = listener.accept();
                if (!a)
                {
                    _policy.log("variable server: " + a.error().message, true);
                    return;
                }
                if (!a.value())
                    return;
                Listener::Accepted& client = *a.value();

                if (!_policy.accepting())
                {
                    // Closing the Fd here gives the client a prompt disconnect.
                    continue;
                }
                if (!_policy.allowed(client.peer))
                {
                    _policy.log("ILLEGAL IP CONNECTION ATTEMPTED: " + client.peer.host() + "\n", true);
                    continue;
                }
                auto connection = TcpConnection::adopt(std::move(client.fd), client.peer, _options);
                if (!connection)
                {
                    _policy.log("variable server: cannot set up a client socket: " + connection.error().message, true);
                    continue;
                }
                _policy.connected(std::move(connection.value()), listener);
            }
        }

        void ListenLoop::send_beacon()
        {
            if (_listeners.empty())
                return;
            const std::string message = _policy.beacon_message(_listeners.front());
            if (message.empty())
                return;
            auto r = _beacon->send(message);
            // Log a beacon error once, not every period.
            const std::string error = r ? std::string() : r.error().message;
            if (!error.empty() && error != _last_beacon_error)
                _policy.log("variable server beacon: " + error, true);
            _last_beacon_error = error;
        }

    } // namespace vs
} // namespace Trick
