// The variable server's listen settings (see VariableServerListenThread.hh). No thread runs
// here; the server's listener reads these settings.

#include "trick/VariableServerListenThread.hh"

#include <cstdlib>
#include <cstring>

Trick::VariableServerListenThread::VariableServerListenThread()
    : Trick::SysThread("VarServListen")
    , _requested_source_address("")
    , _requested_port(0)
    , _user_requested_address(false)
    , _broadcast(true)
{
    cancellable = false;
}

Trick::VariableServerListenThread::~VariableServerListenThread() {}

const char * Trick::VariableServerListenThread::get_hostname() {
    // The old interface returns a copy that the caller frees.
    char * ret = (char *) malloc(_requested_source_address.length() + 1);
    std::memcpy(ret, _requested_source_address.c_str(), _requested_source_address.length() + 1);
    return ret;
}

unsigned short Trick::VariableServerListenThread::get_port() {
    return _requested_port;
}

void Trick::VariableServerListenThread::set_port(unsigned short in_port) {
    _requested_port = in_port;
    _user_requested_address = true ;
}

std::string Trick::VariableServerListenThread::get_user_tag() {
    return _user_tag ;
}

const std::string& Trick::VariableServerListenThread::get_user_tag_ref() {
    return _user_tag ;
}

void Trick::VariableServerListenThread::set_user_tag(std::string in_tag) {
    _user_tag = in_tag ;
}

void Trick::VariableServerListenThread::set_source_address(const char * address) {
    if ( address == NULL ) {
        _requested_source_address = std::string("") ;
    } else {
        _requested_source_address = std::string(address) ;
    }
    _user_requested_address = true;
}

std::string Trick::VariableServerListenThread::get_source_address() {
    return _requested_source_address ;
}

bool Trick::VariableServerListenThread::get_broadcast() {
    return _broadcast;
}

void Trick::VariableServerListenThread::set_broadcast(bool in_broadcast) {
    _broadcast = in_broadcast;
}

bool Trick::VariableServerListenThread::get_user_requested_address() {
    return _user_requested_address ;
}

void Trick::VariableServerListenThread::set_bound_address(const std::string& hostname, unsigned short port) {
    _requested_source_address = hostname ;
    _requested_port = port ;
}

void * Trick::VariableServerListenThread::thread_body() {
    return NULL ;
}

void Trick::VariableServerListenThread::dump( std::ostream & oss ) {
    oss << "Trick::VariableServerListenThread (" << name << ")" << std::endl ;
    oss << "    source_address = " << _requested_source_address << std::endl ;
    oss << "    port = " << _requested_port << std::endl ;
    oss << "    user_requested_address = " << _user_requested_address << std::endl ;
    oss << "    user_tag = " << _user_tag << std::endl ;
    oss << "    broadcast = " << _broadcast << std::endl ;
    Trick::ThreadBase::dump(oss) ;
}
