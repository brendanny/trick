// Trick::VariableServer: the object in the S_define. It keeps the job methods and the
// checkpointed settings, and forwards everything else to the server
// (trick/vs/adapter/Server.hh), which it owns through ServerHandle.

#include "trick/VariableServer.hh"

#include "trick/message_proto.h"
#include "trick/message_type.h"
#include "trick/vs/Address.hh"
#include "trick/vs/AddressFilter.hh"
#include "trick/vs/adapter/Server.hh"

#include <arpa/inet.h>
#include <memory>
#include <netdb.h>
#include <ostream>
#include <sys/socket.h>
#include <unistd.h>

Trick::VariableServer * the_vs ;

Trick::VariableServer::VariableServer()
    : enabled(false)
    , info_msg(false)
    , log(false)
    , session_log(false)
    , allow_connections(false)
    , bypass_ip_check(false)
    , impl(new Trick::vs::adapter::ServerHandle { std::make_shared<Trick::vs::adapter::Server>(*this) })
{
    the_vs = this ;
}

Trick::VariableServer::~VariableServer() {
    if (the_vs == this) {
        the_vs = NULL;
    }
    // A session that did not stop at shutdown keeps its own reference to the server.
    delete impl;
    impl = NULL;
}

std::ostream& Trick::operator<< (std::ostream& s, Trick::VariableServer& vs) {
    s << vs.impl->server->connections_json();
    s.flush();
    return s;
}

// --------------------------------------------------------------------------
// Jobs (default_trick_sys.sm)
// --------------------------------------------------------------------------

int Trick::VariableServer::default_data() { return impl->server->default_data(); }

int Trick::VariableServer::init() { return impl->server->init(); }

int Trick::VariableServer::restart() { return impl->server->restart(); }

int Trick::VariableServer::freeze_init() { return impl->server->freeze_init(); }

void Trick::VariableServer::shutdownConnections() { impl->server->shutdown_connections(); }

int Trick::VariableServer::shutdown() { return impl->server->shutdown(); }

int Trick::VariableServer::get_next_sync_call_time() { return impl->server->get_next_sync_call_time(); }

int Trick::VariableServer::get_next_freeze_call_time() { return impl->server->get_next_freeze_call_time(); }

int Trick::VariableServer::copy_and_write_top() { return impl->server->copy_and_write_top(); }

int Trick::VariableServer::copy_and_write_scheduled() { return impl->server->copy_and_write_scheduled(); }

int Trick::VariableServer::copy_and_write_freeze_scheduled() { return impl->server->copy_and_write_freeze_scheduled(); }

int Trick::VariableServer::copy_and_write_freeze() { return impl->server->copy_and_write_freeze(); }

int Trick::VariableServer::suspendPreCheckpointReload() { return impl->server->suspend_pre_checkpoint_reload(); }

int Trick::VariableServer::resumePostCheckpointReload() { return impl->server->resume_post_checkpoint_reload(); }

void Trick::VariableServer::set_copy_data_job( Trick::JobData * in_job ) {
    impl->server->set_copy_data_job(in_job);
}

void Trick::VariableServer::set_copy_and_write_freeze_job( Trick::JobData * in_job ) {
    impl->server->set_copy_and_write_freeze_job(in_job);
}

// --------------------------------------------------------------------------
// Sockets
// --------------------------------------------------------------------------

int Trick::VariableServer::create_tcp_socket(const char * address, unsigned short in_port) {
    return impl->server->create_tcp_socket(address, in_port);
}

int Trick::VariableServer::create_udp_socket(const char * address, unsigned short in_port) {
    return impl->server->create_udp_socket(address, in_port);
}

int Trick::VariableServer::create_multicast_socket(const char * mcast_address, const char * address,
                                                   unsigned short in_port) {
    return impl->server->create_multicast_socket(mcast_address, address, in_port);
}

const char * Trick::VariableServer::get_hostname() {
    return listen_thread.get_hostname();
}

Trick::VariableServerListenThread & Trick::VariableServer::get_listen_thread() {
    return listen_thread ;
}

// --------------------------------------------------------------------------
// Settings. Each change is copied for the server's threads (config_changed).
// --------------------------------------------------------------------------

bool Trick::VariableServer::get_enabled() {
    return enabled ;
}

void Trick::VariableServer::set_enabled(bool on_off) {
    if (!enabled && on_off)
    {
        message_publish(MSG_INFO,
            "Trick VariableServer: Enabling the Variable Server. See Trick documentation for associated security "
            "concerns.\n");
    }
    enabled = on_off ;
    impl->server->config_changed();
}

bool Trick::VariableServer::get_info_msg() {
    return info_msg ;
}

void Trick::VariableServer::set_var_server_info_msg_on() {
    info_msg = true;
    impl->server->config_changed();
}

void Trick::VariableServer::set_var_server_info_msg_off() {
    info_msg = false;
    impl->server->config_changed();
}

bool Trick::VariableServer::get_log() {
    return log ;
}

bool Trick::VariableServer::get_session_log() {
    return session_log ;
}

void Trick::VariableServer::set_var_server_log_on() {
    log = true;
    impl->server->config_changed();
}

void Trick::VariableServer::set_var_server_log_off() {
    log = false;
    impl->server->config_changed();
}

void Trick::VariableServer::set_var_server_session_log_on() {
    session_log = true;
    impl->server->config_changed();
}

void Trick::VariableServer::set_var_server_session_log_off() {
    session_log = false;
    impl->server->config_changed();
}

bool Trick::VariableServer::set_allow_connections(const bool& b)
{
    if (b)
    {
        message_publish(MSG_WARNING, "Trick VariableServer: Enabling Variable Server Connectivity\n");
        add_ip("127.0.0.1");
    }
    allow_connections = b;
    impl->server->config_changed();
    return allow_connections;
}

bool Trick::VariableServer::get_allow_connections() { return allow_connections; }

bool Trick::VariableServer::set_bypass_ip_check(const bool& b)
{
    if (b)
    {
        message_publish(MSG_WARNING,
            "Trick VariableServer:\nBYPASSING IP SECURITY CHECK.\nANYONE ON THE NETWORK CAN CONNECT TO YOUR PYTHON "
            "INTERPRETER!\nYOU BETTER KNOW WHAT YOU'RE DOING!\n");
    }
    bypass_ip_check = b;
    impl->server->config_changed();
    return bypass_ip_check;
}

bool Trick::VariableServer::get_bypass_ip_check() { return bypass_ip_check; }

const std::set<std::string>& Trick::VariableServer::get_ip_allowlist() { return ip_allowlist; }

void Trick::VariableServer::add_ip(const std::string& ip)
{
    std::string msg = "Trick VariableServer: Adding " + ip + " to the allowlist.\n";
    message_publish(MSG_INFO, msg.c_str());
    ip_allowlist.insert(ip);
    impl->server->config_changed();
}

void Trick::VariableServer::remove_ip(const std::string& ip)
{
    std::string msg = "Trick VariableServer: Removing " + ip + " from the allowlist.\n";
    message_publish(MSG_INFO, msg.c_str());
    ip_allowlist.erase(ip);
    impl->server->config_changed();
}

bool Trick::VariableServer::check_ip(const std::string& ip)
{
    // The same rules the listener uses: IPv4 and IPv6 addresses and CIDR blocks.
    auto address = Trick::vs::Address::parse(ip);
    if (!address)
    {
        return false;
    }
    return Trick::vs::AddressFilter::from(ip_allowlist).allows(*address);
}

void Trick::VariableServer::resolve_hostname()
{
    if (enabled)
    {
        // Add your network IPs to the allowlist
        char hostname[256];
        if (gethostname(hostname, sizeof(hostname)) != 0)
        {
            return;
        }

        struct addrinfo hints { }, *res, *p;
        hints.ai_family   = AF_INET;
        hints.ai_socktype = SOCK_STREAM;

        int status = getaddrinfo(hostname, nullptr, &hints, &res);
        if (status != 0)
        {
            return;
        }

        char ipstr[INET6_ADDRSTRLEN];
        for (p = res; p != nullptr; p = p->ai_next)
        {
            if (p->ai_family == AF_INET)
            {
                struct sockaddr_in* ipv4 = (struct sockaddr_in*)p->ai_addr;
                inet_ntop(p->ai_family, &(ipv4->sin_addr), ipstr, sizeof(ipstr));
                add_ip(ipstr);
            }
        }

        freeaddrinfo(res);
    }
}
