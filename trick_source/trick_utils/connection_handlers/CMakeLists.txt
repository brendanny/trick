trick_utility(trick_connection_handlers ConnectionHandlers)
target_sources(trick_connection_handlers PRIVATE
    ClientConnection.cpp
    MulticastGroup.cpp
    TCPClientListener.cpp
    TCPConnection.cpp
    UDPConnection.cpp
)
target_compile_features(trick_connection_handlers PUBLIC cxx_std_17)
