// The trick.var_* and var_server_* functions (SWIG wraps them; Python calls them).
//
// A session command (var_add, var_send, ...) acts on the session whose line Python is
// running: Server::current_session() on the session's runner thread. Called anywhere else
// (the input file, an event), it does nothing and returns 0, as before.

#include <cstdio>
#include <iostream>
#include <string>

#include "trick/VariableServer.hh"
#include "trick/attributes.h"
#include "trick/map_trick_units_to_udunits.hh"
#include "trick/memorymanager_c_intf.h"
#include "trick/message_proto.h"
#include "trick/message_type.h"
#include "trick/vs/adapter/Server.hh"

extern Trick::VariableServer * the_vs ;

namespace {

    namespace cmd = Trick::vs::cmd;

    /** Give `command` to this thread's session. False if this thread runs no session's line. */
    bool run_in_session(const Trick::vs::Command& command) {
        Trick::vs::Session * session = Trick::vs::adapter::Server::current_session();
        if (session == NULL) {
            return false;
        }
        session->execute(command);
        return true;
    }

    /** Run a session command; the result is always 0, as the old functions returned. */
    int session_command(const Trick::vs::Command& command) {
        run_in_session(command);
        return 0;
    }

    Trick::vs::adapter::Server * server() {
        return Trick::vs::adapter::Server::active();
    }
}

// ----------------------------------------------------------------------------
// Session commands
// ----------------------------------------------------------------------------

int var_add(std::string in_name) { return session_command(cmd::VarAdd { in_name, std::nullopt }); }

int var_add(std::string in_name, std::string in_units) { return session_command(cmd::VarAdd { in_name, in_units }); }

int var_remove(std::string in_name) { return session_command(cmd::VarRemove { in_name }); }

int var_units(std::string var_name , std::string units_name) {
    return session_command(cmd::VarUnits { var_name, units_name });
}

int var_exists(std::string in_name) { return session_command(cmd::VarExists { in_name }); }

int var_get_stl_size(std::string in_name) { return session_command(cmd::VarGetStlSize { in_name }); }

int var_send_once(std::string in_name) { return session_command(cmd::VarSendOnce { in_name, std::nullopt }); }

int var_send_once(std::string in_name, int num) { return session_command(cmd::VarSendOnce { in_name, num }); }

int var_send() { return session_command(cmd::VarSend {}); }

int var_clear() { return session_command(cmd::VarClear {}); }

int var_cycle(double in_rate) { return session_command(cmd::VarCycle { in_rate }); }

int var_pause() { return session_command(cmd::VarPause {}); }

int var_unpause() { return session_command(cmd::VarUnpause {}); }

int var_exit() { return session_command(cmd::VarExit {}); }

int var_validate_address(int on_off) { return session_command(cmd::VarValidateAddress { on_off != 0 }); }

int var_debug(int level) { return session_command(cmd::VarDebug { level }); }

int var_ascii() { return session_command(cmd::VarAscii {}); }

int var_binary() { return session_command(cmd::VarBinary {}); }

int var_binary_nonames() { return session_command(cmd::VarBinaryNoNames {}); }

int var_retry_bad_ref() {
    message_publish(MSG_WARNING,"var_retry_bad_ref has been deprecated\n") ;
    return(0) ;
}

int var_set_copy_mode(int mode) { return session_command(cmd::VarSetCopyMode { mode }); }

int var_set_write_mode(int mode) { return session_command(cmd::VarSetWriteMode { mode }); }

int var_set_send_stdio(int mode) { return session_command(cmd::VarSetSendStdio { mode != 0 }); }

int var_sync(int mode) { return session_command(cmd::VarSync { mode }); }

int var_set_frame_multiple(unsigned int mult) { return session_command(cmd::VarSetFrameMultiple { mult }); }

int var_set_frame_offset(unsigned int offset) { return session_command(cmd::VarSetFrameOffset { offset }); }

int var_set_freeze_frame_multiple(unsigned int mult) {
    return session_command(cmd::VarSetFreezeFrameMultiple { mult });
}

int var_set_freeze_frame_offset(unsigned int offset) {
    return session_command(cmd::VarSetFreezeFrameOffset { offset });
}

int var_byteswap(bool on_off) { return session_command(cmd::VarByteswap { on_off }); }

int var_write_stdio(int stream , std::string text ) {
    // Text from a session's Python line goes to the session (or, if it did not ask for
    // stdio, to the sim's stdout or stderr). Text from anywhere else goes to the sim's.
    if (run_in_session(cmd::VarWriteStdio { stream, text })) {
        return 0;
    }
    std::fputs(text.c_str(), stream == 1 ? stdout : stderr);
    return(0) ;
}

int var_set_client_tag( std::string text ) { return session_command(cmd::VarSetClientTag { text }); }

int var_send_list_size() { return session_command(cmd::VarSendListSize {}); }

int send_sie_resource() { return session_command(cmd::SendSieResource {}); }

int send_sie_class() { return session_command(cmd::SendSieClass {}); }

int send_sie_enum() { return session_command(cmd::SendSieEnum {}); }

int send_sie_top_level_objects() { return session_command(cmd::SendSieTopLevelObjects {}); }

int send_file(std::string file_name) { return session_command(cmd::SendFile { file_name }); }

int var_server_log_on() { return session_command(cmd::VarServerLog { true }); }

int var_server_log_off() { return session_command(cmd::VarServerLog { false }); }

int var_server_session_log_on() {
    if (Trick::vs::Session * session = Trick::vs::adapter::Server::current_session()) {
        session->set_server_session_log(true);
    }
    return 0 ;
}

int var_server_session_log_off() {
    if (Trick::vs::Session * session = Trick::vs::adapter::Server::current_session()) {
        session->set_server_session_log(false);
    }
    return 0 ;
}

// Rewrite decision 3: opt in to VS_IP_ERROR replies.
int var_send_ip_errors(bool on_off) { return session_command(cmd::VarSendIpErrors { on_off }); }

// ----------------------------------------------------------------------------
// var_set
// ----------------------------------------------------------------------------

namespace {
    int var_set_value(const char * var, const cmd::SetValue& value, const char * units) {
        if (var == NULL) {
            var = "";
        }
        cmd::VarSet c { var, value, std::nullopt };
        if (units != NULL) {
            c.units = std::string(units);
        }
        if (server() == NULL) {
            // A sim with no variable server object: assign without the server's lock.
            return Trick::vs::adapter::assign_variable(var, value, units);
        }
        return server()->var_set(c);
    }

    /** var_set with a pointer value that is not NULL (the old V_DATA path). */
    int var_set_pointer( const char * var , void * value , const char * units ) {
        REF2 *ref = ref_attributes(var) ;
        if ( ref == NULL ) {
            message_publish(MSG_WARNING,"reference attributes not found for variable %s in call to var_set\n", var) ;
            return 2;
        }
        int ret = 0;
        if (ref->attr->io & TRICK_VAR_INPUT) {
            V_TREE v_tree ;
            V_DATA v_data ;
            v_tree.v_data = &v_data ;
            v_data.value.vp = value ;
            v_data.type = TRICK_VOID_PTR ;
            if (ref->units != NULL) {
                free(ref->units);
            }
            ref->units = (units != NULL) ? strdup(map_trick_units_to_udunits(units).c_str()) : NULL ;
            ref_assignment(ref , &v_tree) ;
        } else {
            message_publish(MSG_WARNING,"Cannot assign to %s because io_spec does not allow input\n", var) ;
            ret = 1;
        }
        ref_free(ref) ;
        free(ref) ;
        return ret;
    }
}

int var_set( const char  * var , double value , const char * units ) {
    return var_set_value(var, cmd::SetValue(value), units);
}

int var_set( const char  * var , long long value , const char * units ) {
    return var_set_value(var, cmd::SetValue(value), units);
}

int var_set( const char  * var , const char * value , const char * units ) {
    return var_set_value(var, value != NULL ? cmd::SetValue(std::string(value)) : cmd::SetValue(cmd::NoneValue {}),
                         units);
}

int var_set( const char  * var , void * value , const char * units ) {
    if (value == NULL) {
        return var_set_value(var, cmd::SetValue(cmd::NoneValue {}), units);
    }
    if (server() == NULL) {
        return var_set_pointer(var, value, units);
    }
    return server()->write_memory([&] { return var_set_pointer(var, value, units); });
}

// ----------------------------------------------------------------------------
// Server settings
// ----------------------------------------------------------------------------

Trick::VariableServer * var_server_get_var_server() {
    return the_vs ;
}

extern "C" void var_server_list_connections(void) {
    std::cout << *the_vs << std::endl;
}

/**
 * @relates Trick::VariableServer
 * @copydoc Trick::VariableServer::get_hostname
 * C wrapper Trick::VariableServer::get_hostname
 */
extern "C" const char * var_server_get_hostname(void) {
    return the_vs->get_hostname() ;
}

extern "C" unsigned short var_server_get_port(void) {
    return(the_vs->get_listen_thread().get_port()) ;
}

extern "C" void var_server_set_port(unsigned short port) {
    the_vs->get_listen_thread().set_port(port);
}

extern "C" void var_server_set_source_address(const char * source_address) {
    the_vs->get_listen_thread().set_source_address(source_address) ;
}

extern "C" const char * var_server_get_user_tag(void) {
    return(the_vs->get_listen_thread().get_user_tag_ref().c_str()) ;
}

extern "C" void var_server_set_user_tag(const char * in_tag) {
    the_vs->get_listen_thread().set_user_tag(std::string(in_tag));
    if (server() != NULL) {
        server()->config_changed();
    }
}

extern "C" int var_server_get_enabled(void) {
    return(the_vs->get_enabled()) ;
}

extern "C" void var_server_set_enabled(int on_off) {
    the_vs->set_enabled((bool)on_off) ;
}

/** Returns non-zero on failure (the old server returned 0 even then). */
extern "C" int var_server_create_tcp_socket(const char * source_address, unsigned short port) {
    return the_vs->create_tcp_socket(source_address, port) ;
}

/** Returns non-zero on failure (the old server returned 0 even then). */
extern "C" int var_server_create_udp_socket(const char * source_address, unsigned short port) {
    return the_vs->create_udp_socket(source_address, port) ;
}

extern "C" int var_server_create_multicast_socket(const char * mcast_address,
 const char * source_address, unsigned short port) {
    return the_vs->create_multicast_socket(mcast_address, source_address, port) ;
}

void var_allow_connections()
{
    var_server_set_enabled(true);
    the_vs->set_allow_connections(true);
}

void var_disable_connections()
{
    var_server_set_enabled(false);
    the_vs->set_allow_connections(false);
}

void var_allow_all_connections()
{
    var_allow_connections();
    the_vs->set_bypass_ip_check(true);
}

void var_resolve_hostname() { the_vs->resolve_hostname(); }

bool var_set_allow_connections(bool b) { return the_vs->set_allow_connections(b); }

bool var_get_allow_connections() { return the_vs->get_allow_connections(); }

int var_set_ip_check_bypass(bool b) { return the_vs->set_bypass_ip_check(b); }

int var_get_ip_check_bypass() { return the_vs->get_bypass_ip_check(); }

void var_add_ip(const std::string& ip) { the_vs->add_ip(ip); }

void var_remove_ip(const std::string& ip) { the_vs->remove_ip(ip); }

// Rewrite decision 4: turn the Python fallback off (typed commands only).
void var_server_set_python_commands(bool on_off) {
    if (server() != NULL) {
        server()->set_python_commands(on_off);
    }
}

bool var_server_get_python_commands() { return server() != NULL && server()->python_commands(); }
