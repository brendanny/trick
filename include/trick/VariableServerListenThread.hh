/*
    PURPOSE:
        (The variable server's listen settings: source address, port, user tag and beacon.
         The rewritten variable server (rewrite decision 5) keeps this class so that the
         settings stay checkpointed at the same paths, for example
         trick_vs.vs.listen_thread._requested_port. No thread runs here: the variable
         server's listener reads these settings. It stays a SysThread so that old checkpoints,
         which hold the thread's fields, still load, and so that var_server_cpu_set (the CPU
         set of this object) still sets the CPUs of the variable server's threads.)
*/

#ifndef VARIABLESERVERLISTENTHREAD_HH
#define VARIABLESERVERLISTENTHREAD_HH

#include <string>
#include <iostream>
#include "trick/SysThread.hh"

namespace Trick {

/**
  The variable server's listen settings.
  @author Alex Lin
  @author Jackie Deans (2023)
 */
    class VariableServerListenThread : public Trick::SysThread {

        public:
            VariableServerListenThread() ;

            virtual ~VariableServerListenThread() ;

            /** The host name or address the variable server listens on. The caller frees the copy. */
            const char * get_hostname() ;

            /** The port the variable server listens on (the requested port before initialization). */
            unsigned short get_port() ;

            /** Request a listen port (var_server_set_port). */
            void set_port(unsigned short in_port) ;

            std::string get_user_tag() ;
            const std::string& get_user_tag_ref() ;
            void set_user_tag(std::string in_tag) ;

            /** Request a source address (var_server_set_source_address). "::" turns IPv6 on. */
            void set_source_address(const char * address) ;
            std::string get_source_address() ;

            /** Send the multicast beacon (on by default). */
            bool get_broadcast() ;
            void set_broadcast(bool in_broadcast) ;

            /** True if the input file set the port or source address. */
            bool get_user_requested_address() ;

            /** Record the address the listen socket was bound to. */
            void set_bound_address(const std::string& hostname, unsigned short port) ;

            /** No thread runs here; this returns at once. */
            virtual void * thread_body() ;

            virtual void dump( std::ostream & oss = std::cout ) ;

        protected:
            /** Requested or bound source address */
            std::string _requested_source_address ;       /**<  trick_units(--) */

            /** Requested or bound port */
            unsigned short _requested_port ;       /**<  trick_units(--) */

            /** User requested specific port or source address */
            bool _user_requested_address ;  /**<  trick_units(--) */

            /** User defined unique tag to easily identify this simulation. */
            std::string _user_tag;          /**<  trick_units(--) */

            /** Turn on/off broadcasting of variable server port. */
            bool _broadcast ;       /**<  trick_units(--) */
    } ;

}

#endif
