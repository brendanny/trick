
#include "trick/VariableServer.hh"
#include "trick/vs/adapter/Server.hh"

int Trick::VariableServer::default_data() {
    if (impl != NULL) {
        return impl->server->default_data();
    }

    return listen_thread.init_listen_device() ;
}

