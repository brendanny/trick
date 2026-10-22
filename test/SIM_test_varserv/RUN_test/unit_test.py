import trick
from trick.unit_test import *


def main():

    # The variable server is disabled and refuses connections by default.
    trick.var_allow_connections()
    # UDP and multicast sessions check the allowlist against an address that
    # is not set until a datagram arrives, so they reject themselves at start
    # ("ILLEGAL IP CONNECTION ATTEMPTED: 0.0.0.0"). Bypass the check until the
    # variable server rewrite fixes this.
    trick.var_set_ip_check_bypass(True)

    trick.var_server_set_port(40000)
    trick.real_time_enable()
    trick.exec_set_software_frame(0.01)
    # trick.set_var_server_info_msg_on()
    trick.set_var_server_log_on()

    hostname = trick.var_server_get_hostname()

    trick.var_server_create_tcp_socket(hostname, 49000)
    # Bind the UDP and multicast servers to loopback, not to the hostname.
    # The hostname binds to INADDR_ANY, so the multicast server receives its
    # own output from the group and runs it as Python. It filters its own
    # messages by comparing the sender with gethostbyname(hostname), which
    # fails on hosts where the hostname resolves to 127.0.0.1. The test
    # client sends to 127.0.0.1 in all cases.
    trick.var_server_create_udp_socket("127.0.0.1", 48000)
    trick.var_server_create_multicast_socket("224.10.10.10", "127.0.0.1", 47000)

    # The test client stops the SIM when it finishes. This limit only ends a
    # run whose client hangs; sanitizer builds need more than 100 s.
    trick.exec_set_terminate_time(400.0)

    varServerPort = trick.var_server_get_port()
    test_output = os.getenv("TRICK_HOME") + "/trick_test/SIM_test_varserv.xml"
    command = (
        'os.system("./models/test_client/test_client '
        + str(varServerPort)
        + " --gtest_output=xml:"
        + test_output
        + ' &")'
    )

    # Start the test client after everything has been initialized (hopefully)
    trick.add_read(1.0, command)


if __name__ == "__main__":
    main()
