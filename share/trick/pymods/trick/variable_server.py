"""
This module contains tools for communicating with a sim's variable
server, primarily via the Variable and VariableServer classes. See
https://github.com/nasa/trick/wiki/Python-Variable-Server-Client for
a tutorial and examples.

It needs Python 3.11 or later.
"""

from __future__ import annotations

import enum
import os
import re
import socket
import struct
import threading
import time
from collections import namedtuple
from dataclasses import dataclass, field
from typing import Any, Callable, NamedTuple, TextIO


class VariableServerError(Exception):
    """
    Variable Server communication I/O error.
    """


class UnitsConversionError(VariableServerError):
    """
    Raised when a units conversion fails.

    Attributes
    ----------
    name : str
        The name of the variable for which the conversion failed.
    units : str
        The units to which the variable could not be converted.
    """

    def __init__(self, name: str, units: str | None) -> None:
        super().__init__(f"[{name}] cannot be converted to [{units}]")
        self.name = name
        self.units = units


class UnexpectedMessageError(VariableServerError):
    """
    Raised when a received message is not of the expected type.

    Attributes
    ----------
    expected_id : int
        The expected message indicator.
    actual_id : int
        The actual message indicator.
    """

    def __init__(self, expected_id: int, actual_id: int) -> None:
        super().__init__(
            f"Unexpected message received. Expected ID = {int(expected_id)}. "
            f"Actual ID = {int(actual_id)}"
        )
        self.expected_id = expected_id
        self.actual_id = actual_id


class ValueCountError(VariableServerError):
    """
    Raised when the number of received variable values does not match
    the expected count.

    Attributes
    ----------
    expected : int
        The expected count.
    actual : int
        The actual count.
    """

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(
            f"Number of values received ({actual}) does not match expected ({expected})"
        )
        self.expected = expected
        self.actual = actual


def _create_enum(name: str, field_names: list[str], ordinal_values: bool = True) -> Any:
    """
    Create a namedtuple with automatic values. Kept for code that used
    it; this module now uses the enum module.

    Parameters
    ----------
    name : str
        The name of the namedtuple.
    field_names : iterable of str
        The field names.
    ordinal_values : bool
        True to assign each field an ordinal number, starting at 0. This
        creates a classic number-based enum.
        False to use the field names themselves as the values for the
        fields. This creates a string-based enum.
    """
    return namedtuple(name, field_names)(*(range(len(field_names)) if ordinal_values else field_names))


class _Indicator(enum.IntEnum):
    """
    The message types the variable server sends. The values are
    VS_MESSAGE_TYPE in variable_server_message_types.h.
    """

    IP_ERROR = -1  # after trick.var_send_ip_errors(True)
    VAR_SEND = 0
    VAR_EXISTS = 1
    SIE_RESOURCE = 2
    LIST_SIZE = 3
    STDIO = 4
    SEND_ONCE = 5
    VAR_GET_STL_SIZE = 6


class _MessageFields(NamedTuple):
    indicator: int
    data: str


class Message(_MessageFields):
    """
    A message from the variable server.

    Attributes
    ----------
    indicator : int
        The indicator.
    data : str
        The rest of the message.
    """

    __slots__ = ()

    # Message.Indicator.VAR_SEND and so on.
    Indicator = _Indicator


@dataclass(eq=False)
class Variable:
    """
    A variable whose value and units will be updated from the sim. You
    should not directly change any part of this class.

    Two Variables are equal only if they are the same object, so a
    VariableServer can sample two Variables with the same name.

    Attributes
    ----------
    name : str
        The fully-qualified name.
    units : str
        The units. Use 'xx' to specify default units.

    Properties
    ----------
    value : type returned by the type_ parameter of __init__ (or None)
        The value.
    """

    name: str
    units: str | None = None
    # A callable that accepts one argument and is used to convert the
    # stringified value from the variable server to the desired type.
    # This can be a builtin like int or float or a custom function that
    # does anything you like!
    type_: Callable[[Any], Any] = field(default=str, repr=False)
    _value: Any = field(default=None, init=False, repr=False)

    @property
    def value(self) -> Any:
        """
        Get the converted value.
        """
        return self.type_(self._value)

    @value.setter
    def value(self, value: Any) -> None:
        """
        Set the value.
        """
        self._value = value

    @property
    def _type(self) -> Callable[[Any], Any]:
        # The name before Python 3.11; kept for code that read it.
        return self.type_

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        units = f" {self.units}" if self.units is not None else ""
        return f"{self.name} = {self.value}{units}"


class _Channel(enum.StrEnum):
    """Which of the two connections a command goes to."""

    ASYNC = "ASYNC"
    SYNC = "SYNC"
    BOTH = "BOTH"


class _CopyMode(enum.IntEnum):
    """How the variable server copies values (var_set_copy_mode)."""

    ASYNC = 0
    SCHEDULED = 1
    TOP_OF_FRAME = 2


class VariableServer:
    """
    Send commands to and receive responses from a simulation's
    variable server.

    You must call close on instances of this class to release resources
    allocated during initialization.
    """

    Channel = _Channel
    CopyMode = _CopyMode

    def __init__(self, hostname: str, port: int | str) -> None:
        """
        Create a connection to the simulation variable server at
        host:port.

        Parameters
        ----------
        hostname : str
            The name of the machine that is running the simulation to
            which you want to connect.
        port : int
            The port on which the simulation's variable server is
            listening.
        """
        self._variables: list[Variable] = []
        self._callbacks: dict[Callable[..., Any], tuple[Any, dict[str, Any]]] = {}
        self._error_callbacks: dict[Callable[..., Any], tuple[Any, dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._open = False
        port = int(port)
        self._synchronous_socket = socket.create_connection((hostname, port))
        self._asynchronous_socket = socket.create_connection((hostname, port))
        self._synchronous_file_interface: TextIO = self._synchronous_socket.makefile()
        self._asynchronous_file_interface: TextIO = self._asynchronous_socket.makefile()
        self._open = True
        self.pause(channel=self.Channel.SYNC)

        # Start a thread that listens for data from the variable server,
        # updates the variables being sampled, and notifies listeners.
        # This thread can only be terminated by calling close. A Python
        # process cannot terminate while non-daemon threads are running,
        # so make this thread a daemon in case the user fails to call
        # close when finished with this instance.
        self._thread = threading.Thread(
            target=self._update_variables, name="Asynchronous Variable Sampler", daemon=True
        )
        self._thread.start()

    def _update_variables(self) -> None:
        """
        Continuously update variables (the sampling thread).
        """
        while True:
            try:
                values = self._read_values(False)
            except Exception as exception:
                if self._open:
                    for function, args in list(self._error_callbacks.items()):
                        function(*args[0], exception=exception, **args[1])
                return
            # We must lock here to ensure that variables are not
            # removed while we are processing an update.
            with self._lock:
                # If there are more values than variables, it must
                # be that a variable was removed after this message
                # was sent but before we processed it. Variables can
                # be removed from any place within the list, so we
                # don't know which "extra" values to ignore.
                # We therefore discard the entire message.
                #
                # If there are fewer values than variables, it must
                # be that a variable was added after this message
                # was sent but before we processed it. Variables
                # can only be appended to the list, so we know that
                # any missing values are for variables at the end of
                # the list. We can therefore still use all the
                # values to update variables at the front of the
                # list.
                #
                # We could still end up assigning values to the
                # wrong variables if someone removed AND added
                # variables after a message was sent but before we
                # processed it, but the probability of someone
                # doing that doesn't justify the work at this point.
                # Besides, it would be corrected with the next
                # message.
                if len(values) <= len(self._variables):
                    for variable, value in zip(self._variables, values):
                        variable.value, variable.units = _parse_value(value)

                    for function, args in list(self._callbacks.items()):
                        function(*args[0], **args[1])

    def __del__(self) -> None:
        """
        Call close in case the user forgot. Don't rely on this to clean
        up for you. You should really explicitly call close yourself.
        """
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self) -> VariableServer:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def get_value(self, name: str, units: str | None = None, type_: Callable[[Any], Any] = str) -> Any:
        """
        Get the value of the named variable. If units are specified, the
        value is converted if possible. This function provides a simple
        interface and is most useful when you just want to get the value
        of one variable and don't require periodic sampling. For a more
        powerful but complex function, see get_values. To sample values
        periodically, see add_variables.

        Parameters
        ----------
        name, units, and type_ are as documented in Variable.

        Returns
        -------
        type returned by type_
            The result of calling type_ on the variable's value.

        Raises
        ------
        IOError
            If the remote endpoint has closed the connection.
        UnexpectedMessageError
            If the next message is not a set of variable values.
        ValueCountError
            If more than one value is received.
        UnitsConversionError
            If units are specified and the conversion fails.
        Additional errors may be raised by type_.

        Examples
        --------
        Get value (default type is string):
        >>> from variable_server import VariableServer
        >>> with VariableServer('localhost', 7000) as vs:
        ...     vs.get_value('ball.state.input.position[0]')
        '5'

        Get value as an int:
        >>> from variable_server import VariableServer
        >>> with VariableServer('localhost', 7000) as vs:
        ...     vs.get_value('ball.state.input.position[0]',
        ...     type_=int)
        5

        Get value as a float in millimeters:
        >>> from variable_server import VariableServer
        >>> with VariableServer('localhost', 7000) as vs:
        ...     vs.get_value('ball.state.input.position[0]',
        ...     units='mm', type_=float)
        5000.0

        Convert value with custom function:
        >>> from variable_server import VariableServer
        >>> with VariableServer('localhost', 7000) as vs:
        ...     vs.get_value('ball.state.input.position[0]',
        ...     type_=lambda x: int(x) * 2)
        10
        """

        # add the variable and poll its value
        self._var_add(name, units, self.Channel.SYNC)
        self._var_send()
        self._var_clear(self.Channel.SYNC)

        # make sure we only got one
        values = self._read_values()
        _assert_value_count(1, len(values))

        # check for units conversion
        value, actual_units = _parse_value(values[0])
        _assert_units_conversion(name, units, actual_units)

        return type_(value)

    def get_stl_size(self, name: str) -> int:
        """
        Get the size of the STL container with the given name. This only
        works for STL containers for which the variable server provides
        size information via the var_get_stl_size function. Supported
        container types are currently std::vector, std::deque, and std::array.
        This function can be used for getting the size of a container
        before using get_value or get_values to get the values of its
        elements or checking the boundary of the container.

        Parameters
        ----------
        name : str
            The fully-qualified name of the STL container variable.

        Returns
        -------
        int
            The size of the container.

        Raises
        ------
        IOError
            If the remote endpoint has closed the connection.
        UnexpectedMessageError
            If the next message is not a VAR_GET_STL_SIZE message.
        ValueCountError
            If more than one value is received.
        Additional errors may be raised by int.
        """

        # request the size and read the response
        self.send(f'trick.var_get_stl_size("{name}")')
        return self._read_stl_size()

    def set_value(self, name: str, value: Any, units: str | None = None) -> None:
        """
        Set the value of the named variable. If units are specified, the
        value is converted if possible. If the conversion fails, the
        value is unchanged, and no error is raised.

        Attributes
        ----------
        name : str
            The fully-qualified name.
        value : any
            The value. This should be of the type expected by the
            variable server.
        units : str
            The units.
        """
        text = f'"{value}"' if isinstance(value, str) else value
        units_text = f', "{units}"' if units is not None else ""
        self.send(f'trick.var_set("{name}", {text}{units_text})')

    def get_values(self, *variables: Variable) -> list[Any]:
        """
        Get the values of variables. If units are specified, values are
        converted if possible. Each argument is also updated in place,
        so you can ignore the returned list of values if you were just
        going to store them anyway. The list is useful, for example, for
        inlining the results, eliminating the need to update and use
        the variables in separate statements.

        This function is more efficient than calling get_value
        for each variable, but has a steeper learning curve. It is most
        useful when you want to fetch multiple variables' values and
        units and don't require periodic sampling. To sample values
        periodically, see add_variables.

        Parameters
        ----------
        variables : zero or more Variables
            The variables for which to fetch values and units.

        Returns
        -------
        [any]
            A list of the requested values in order. The type of each
            element is that returned by the corresponding Variable's
            type_.

        Raises
        ------
        IOError
            If the remote endpoint has closed the connection.
        UnexpectedMessageError
            If the next message is not a set of variable values.
        ValueCountError
            If the number of received values does not match the number
            of variables.
        UnitsConversionError
            If units are specified and the conversion fails. In this
            case, variables before the error will have been updated,
            but variables after will not. The variable for which the
            error occurred will not be updated.
        Additional errors may be raised by each Variables's type_, but
        they do not prevent the rest of the Variables from being
        updated. Variables whose type_ conversion fails will raise an
        error every time their value property is accessed.

        Example
        -------
        >>> from variable_server import Variable, VariableServer
        >>> position = Variable('ball.state.input.position[0]',
        ... type_=int)
        >>> mass = Variable('ball.state.input.mass', units='g',
        ... type_=float)
        >>> with VariableServer('localhost', 7000) as vs:
        ...     vs.get_values(position, mass)
        [5, 10000.0]
        >>> position
        ball.state.input.position[0] = 5 m
        >>> mass
        ball.state.input.mass = 10000.0 g
        """

        # check for zero arguments
        if not variables:
            return []

        # add all the variables and poll their values
        for variable in variables:
            self._var_add(
                variable.name,
                variable.units if variable.units is not None else "xx",
                self.Channel.SYNC,
            )
        self._var_send()
        self._var_clear(self.Channel.SYNC)

        # make sure we got as many as expected
        values = self._read_values()
        _assert_value_count(len(variables), len(values))

        # update each Variable, checking units conversions
        for variable, entry in zip(variables, values):
            value, units = _parse_value(entry)
            if variable.units is not None:
                _assert_units_conversion(variable.name, variable.units, units)
            else:
                variable.units = units
            variable.value = value

        return [variable.value for variable in variables]

    def add_variables(self, *variables: Variable) -> None:
        """
        Immediately update and begin periodically sampling the given
        variables. This class retains references to all passed-in
        variables and updates their values and units when new values
        arrive from the variable server. All sampling is performed on a
        separate thread, but accessing a variable's fields is always
        safe. Adding variables which are already being sampled has no
        effect. To set the sampling period, see set_period. To register
        a function to be called whenever variables are updated, see
        register_callback.

        Parameters
        ----------
        variables : zero or more Variables
            The variables to begin sampling.

        Raises
        ------
        IOError
            If the remote endpoint has closed the connection.
        UnexpectedMessageError
            If the next message is not a set of variable values.
        ValueCountError
            If the number of received values does not match the number
            of variables.
        UnitsConversionError
            If units are specified and the conversion fails. In this
            case, variables before the error will have been updated,
            but variables after will not. The variable for which the
            error occurred will not be updated.
        Additional errors may be raised by each Variables's type_, but
        they do not prevent the rest of the Variables from being
        updated. Variables whose type_ conversion fails will raise an
        error every time their value property is accessed.

        If any error occurs, no variables are scheduled for sampling.
        """

        # remove existing variables
        new_variables = [variable for variable in variables if variable not in self._variables]

        # check for type_ and units conversion errors
        self.get_values(*new_variables)

        for variable in new_variables:
            # No lock is needed here because:
            # - appending to the variables list while
            #   _update_variables is executing does not invalidate
            #   the length check
            # - zip is bounded by the number of values, and the
            #   length check ensures there are at least as many
            #   variables as values
            self._variables.append(variable)
            self._var_add(variable.name, variable.units if variable.units is not None else "xx")

    def remove_variables(self, *variables: Variable) -> None:
        """
        Stop sampling the given variables. Removing variables that are
        not being sampled has no effect.

        Parameters
        ----------
        variables : zero or more Variables
            The variables to stop sampling.
        """
        for variable in variables:
            if variable in self._variables:
                # Variables must not be removed while _update_variables
                # is processing an update. See its comment for an
                # explanation.
                with self._lock:
                    self._variables.remove(variable)
                self._var_remove(variable.name)

    def remove_all_variables(self) -> None:
        """
        Stop sampling all variables. To merely suspend sampling,
        see pause.
        """
        self._var_clear()
        # No lock is needed here because:
        # - This assignment is atomic.
        # - If _update_variables has already called zip, the list it is
        #   iterating over is unchanged as we're assigning a new list
        #   here instead of clearing the shared reference.
        # - If _update_variables has not yet called zip, when it does,
        #   zip will return an empty generator, terminating the loop.
        self._variables = []

    def set_units(self, name: str, units: str) -> None:
        """
        Set the units in which the named variable is sampled. This only
        applies to Variables being periodically sampled.
        See add_variables.

        Parameters
        ----------
        name : str
            The variable's name.
        units : str
            The units to which to convert the sampled value.
        """
        self.send(f'trick.var_units("{name}", "{units}")', self.Channel.ASYNC)

    def set_period(self, period: float) -> None:
        """
        Set the sampling period (in seconds).

        Parameters
        ----------
        period : float
            The inverse of the rate (in Hz) at which you want to sample
            variable values.
        """
        self.send(f"trick.var_cycle({float(period)})", self.Channel.ASYNC)

    def register_callback(
        self,
        function: Callable[..., Any],
        args: Any = None,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        """
        Call function whenever new variable values are sampled.
        Registering an already-registered function replaces its existing
        registration. The order in which functions are called is not
        specified. Functions are executed on the asynchronous sampling
        thread.

        Parameters
        ----------
        function : callable
            The function to call.
        args : tuple
            The positional arguments to be passed to the function.
        kwargs : dict
            The keyword arguments to be passed to the function.
        """
        self._callbacks[function] = (args if args is not None else [], kwargs if kwargs is not None else {})

    def deregister_callback(self, function: Callable[..., Any]) -> None:
        """
        Do not call function whenever new variable values are sampled.
        Deregistering an unregistered function has no effect.

        Parameters
        ----------
        function : any
            A function previously added via register_callback.
        """
        self._callbacks.pop(function, None)

    def register_error_callback(
        self,
        function: Callable[..., Any],
        args: Any = None,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        """
        Call function if an error occurs while sampling variable values.
        Registering an already-registered function replaces its existing
        registration. The order in which functions are called is not
        specified. Functions are executed on the asynchronous sampling
        thread.

        Parameters
        ----------
        function : callable
            The function to call. It must accept a keyword argument
            named 'exception' which will contain the error.
        args : tuple
            The positional arguments to be passed to the function.
        kwargs : dict
            The keyword arguments to be passed to the function.
        """
        self._error_callbacks[function] = (
            args if args is not None else [],
            kwargs if kwargs is not None else {},
        )

    def deregister_error_callback(self, function: Callable[..., Any]) -> None:
        """
        Do not call function if an error occurs while sampling variable
        values. Deregistering an unregistered function has no effect.

        Parameters
        ----------
        function : any
            A function previously added via register_error_callback.
        """
        self._error_callbacks.pop(function, None)

    def pause(self, pause: bool = True, channel: _Channel | str = _Channel.ASYNC) -> None:
        """
        Pause or unpause sampling.

        Parameters
        ----------
        pause : bool
            True to pause sampling.
            False to resume sampling.
        channel : Channel
            The channel to affect. You should almost certainly leave
            this as the default.
        """
        self.send(f"trick.var_{'' if pause else 'un'}pause()", channel)

    def set_debug(self, level: int, channel: _Channel | str = _Channel.BOTH) -> None:
        """
        Set the debugging level. This effects how much information the
        sim's variable server outputs to the sim's standard output
        stream. It is not a debugging option for this Python class and
        does not produce output on this process.

        Parameters
        ----------
        level : int
            The debugging level. 0 = no debugging.
        channel : Channel
            The channel to affect.
        """
        self.send(f"trick.var_debug({int(level)})", channel)

    def set_tag(self, tag: str) -> None:
        """
        Set the identifier for this variable server client. The tag is
        used in log files to associate each message with its sender.

        Parameters
        ----------
        tag : str
            An identifier for this client.
        """
        for channel in (self.Channel.SYNC, self.Channel.ASYNC):
            self.send(f'trick.var_set_client_tag("{tag}_{channel}")', channel)

    def set_copy_mode(
        self, mode: _CopyMode | int = _CopyMode.ASYNC, channel: _Channel | str = _Channel.BOTH
    ) -> None:
        """
        Set the method by which variable values are copied.

        Parameters
        ----------
        mode : CopyMode
            ASYNC
            Values are copied by an independent thread. This has no
            effect on simulation execution, but values within a set may
            not all be from the same sim frame.

            SCHEDULED
            Values are copied as an automatic_last job in the sim's main
            thread. Values within a set are guaranteed to be from the
            same sim frame.

            TOP_OF_FRAME
            Values are copied at the top of each sim frame in the main
            thread. Values within a set are guaranteed to be from the
            same sim frame.

        channel : Channel
            The channel to affect.
        """
        self.send(f"trick.var_set_copy_mode({int(mode)})", channel)

    def send_on_copy(self, enable: bool = True) -> None:
        """
        Set the method by which variable values are sent.

        Parameters
        ----------
        enable : bool
            True to cause the variable server to send variable values
            as soon as the sim's main thread copies them (copy modes
            SCHEDULED and TOP_OF_FRAME). The values are sent by the
            session's own thread; the main thread does not wait for the
            send.
            False to send values on the session's own cycle.
        """
        self.send(f"trick.var_set_write_mode({bool(enable)})", self.Channel.ASYNC)

    def validate_addresses(self, validate: bool = True, channel: _Channel | str = _Channel.BOTH) -> None:
        """
        Set whether or not addresses are validated.

        When bool(validate) is True, variable addresses will be
        validated against the memory manager before being read. Those
        not known to Trick are considered invalid and their values are
        reported as "BAD_REF". This prevents malformed variable
        requests, such as pointers with invalid offsets, from causing
        segmentation faults.

        Parameters
        ----------
        validate : bool
            The desired validation state.
        channel : Channel
            The channel to affect.
        """
        self.send(f"trick.var_validate_address({bool(validate)})", channel)

    def variable_exists(self, name: str) -> bool:
        """
        Determine if name is known to the memory manager.

        Parameters
        ----------
        name : str
            The variable's name.

        Returns
        -------
        bool
            True if name has been registered with the memory manager.
            False if not.

        Raises
        ------
        IOError
            If the remote endpoint has closed the connection.
        UnexpectedMessageError
            If the next message on the synchronous channel is not a
            response to a var_exists inquiry.
        """
        self.send(f'trick.var_exists("{name}")')
        message = self.readline()
        _assert_message_type(message, Message.Indicator.VAR_EXISTS)
        return message.data == "1"

    def freeze(self, freeze: bool = True) -> None:
        """
        Freeze or unfreeze the sim.

        Parameters
        ----------
        freeze : bool
            True to freeze the sim.
            False to unfreeze it.
        """
        self.send(f"trick.exec_{'freeze' if bool(freeze) else 'run'}()")

    def checkpoint(self, filename: str) -> None:
        """
        Dump a checkpoint.

        Parameters
        ----------
        filename : str
            The checkpoint file name. The checkpoint will be saved in the
            directory containing the sim's input file.
        """
        self.send(f'trick.checkpoint("{filename}")')

    def load_checkpoint(self, filename: str) -> None:
        """
        Load a checkpoint. The path is relative to the directory containing
        the sim's S_main executable.

        Parameters
        ----------
        filename : str
            The checkpoint file name.
        """
        self.send(f'trick.load_checkpoint("{filename}")')

    def enable_real_time(self, enable: bool = True) -> None:
        """
        Toggle real-time execution.

        Parameters
        ----------
        enable : bool
            True so synchronize sim execution with the real-time clock.
            False to run as quickly as possible.
        """
        self.send(f"trick.real_time_{'en' if bool(enable) else 'dis'}able()")

    def send(self, command: str, channel: _Channel | str = _Channel.SYNC) -> None:
        """
        Append a newline to command and send it, blocking until all data
        has been sent. Calling this directly is only necessary if you
        want to send a command for which there is not already a method
        in this class. You must not send a command on the asynchronous
        channel that produces a response, as the response will be
        consumed by the variable-sampling thread, which will likely
        cause an error. You must ensure the socket is left in a "clean"
        state before calling other methods of this class. If incoming
        data is left on either channel, it is likely to cause other
        methods to fail since they won't get what they're expecting when
        they go to read.

        Parameters
        ----------
        command : str
            The command to send.
        channel : Channel
            The channel on which to send. You should almost certainly
            leave this as the default.
        """
        data = f"{command}\n".encode()
        sockets = {
            self.Channel.SYNC: [self._synchronous_socket],
            self.Channel.ASYNC: [self._asynchronous_socket],
            self.Channel.BOTH: [self._synchronous_socket, self._asynchronous_socket],
        }[_Channel(channel)]
        for sock in sockets:
            sock.sendall(data)

    def readline(self, synchronous_channel: bool = True) -> Message:
        """
        Read a newline-terminated line, blocking if necessary. Calling
        this directly is only necessary if you have directly called
        send and expect a response from the variable server. The newline
        character is stripped.

        Parameters
        ----------
        synchronous_channel : bool
            True to read from the synchronous channel.
            False to read from the asynchronous channel.

        Returns
        -------
        Message
            The next available message.

        Raises
        ------
        IOError
            If the remote endpoint has closed the connection.
        """
        file_interface = (
            self._synchronous_file_interface if synchronous_channel else self._asynchronous_file_interface
        )
        line = file_interface.readline()
        if not line:
            raise IOError("The remote endpoint has closed the connection")
        indicator, _, data = line.rstrip(os.linesep).partition("\t")
        return Message(int(indicator), data)

    def _var_add(self, name: str, units: str | None = None, channel: _Channel | str = _Channel.ASYNC) -> None:
        """
        Send a var_add command to the variable server.

        Parameters
        ----------
        name : str
            The variable's name.
        units : str
            The units in which to report the variable's value.
        channel : Channel
            The channel to affect.
        """
        units_text = f', "{units}"' if units is not None else ""
        self.send(f'trick.var_add("{name}"{units_text})', channel)

    def _var_remove(self, name: str) -> None:
        """
        Send a var_remove command to the variable server.

        Parameters
        ----------
        name : str
            The variable's name.
        """
        self.send(f'trick.var_remove("{name}")', self.Channel.ASYNC)

    def _var_send(self, channel: _Channel | str = _Channel.SYNC) -> None:
        """
        Send a var_send command to the variable server.

        Parameters
        ----------
        channel : Channel
            The channel to affect.
        """
        self.send("trick.var_send()", channel)

    def _read_values(self, synchronous_channel: bool = True) -> list[str]:
        """
        Read a set of variable values.

        Parameters
        ----------
        synchronous_channel : bool
            True to read from the synchronous channel.
            False to read from the asynchronous channel.

        Returns
        -------
        [str]
            A list of values, which may include units.

        Raises
        ------
        IOError
            If the remote endpoint has closed the connection.
        UnexpectedMessageError
            If the next message is not a set of variable values.
        """
        message = self.readline(synchronous_channel)
        _assert_message_type(message, Message.Indicator.VAR_SEND)
        return message.data.split("\t")

    def _read_stl_size(self) -> int:
        """
        Read the size of an STL container.

        Returns
        -------
        int
            The size of the container.

        Raises
        ------
        IOError
            If the remote endpoint has closed the connection.
        UnexpectedMessageError
            If the next message is not a VAR_GET_STL_SIZE message.
        ValueCountError
            If more than one value is received.
        Additional errors may be raised by int.
        """
        message = self.readline()
        _assert_message_type(message, Message.Indicator.VAR_GET_STL_SIZE)
        values = message.data.split("\t")
        _assert_value_count(1, len(values))
        return int(values[0])

    def _var_clear(self, channel: _Channel | str = _Channel.ASYNC) -> None:
        """
        Send a var_clear command to the variable server.

        Parameters
        ----------
        channel : Channel
            The channel to affect.
        """
        self.send("trick.var_clear()", channel)

    def close(self) -> None:
        """
        Close the connection and release resources. No methods can be
        called after this one. A new connection can be established only
        by creating a new instance.
        """
        if not getattr(self, "_open", False):
            return
        # self._asynchronous_file_interface.close() hangs if shutdown
        # isn't called first: self._thread is always blocked on a read
        # from the asynchronous socket.
        self._open = False
        for sock in (self._synchronous_socket, self._asynchronous_socket):
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass  # the sim already closed it
        self._synchronous_file_interface.close()
        self._asynchronous_file_interface.close()
        self._synchronous_socket.close()
        self._asynchronous_socket.close()
        if self._thread is not threading.current_thread():
            self._thread.join()

    def __str__(self) -> str:
        return "VariableServer" + str(self._synchronous_socket.getpeername())


def find_simulation(
    host: str | None = None,
    port: int | None = None,
    user: str | None = None,
    pid: int | None = None,
    version: str | None = None,
    sim_directory: str | None = None,
    s_main: str | None = None,
    input_file: str | None = None,
    tag: str | None = None,
    timeout: float | None = None,
) -> VariableServer:
    """
    Listen for simulations on the multicast channel over which all sims broadcast
    their existence. Connect to the one that matches the provided arguments that
    are not None.

    If there are multiple matches, connect to the first one we happen to find.
    If all arguments are None, connect to the first sim we happen to find.
    Such matches will be non-deterministic.

    Parameters
    ----------
    host : str
        Host name of the machine on which the sim is running as reported by
        Trick.
    port : int
        Variable Server port.
    user : str
        Simulation process user.
    pid : int
        The sim's process ID.
    version : str
        Trick version.
    sim_directory : str
        SIM_* directory. If this starts with /, it will be considered an
        absolute path.
    s_main : str
        Filename of the S_main* executable. Not an absolute path.
    input_file : str
        Path to the input file relative to the simDirectory.
    tag : str
        Simulation tag.
    timeout : positive float or None
        How long to look for the sim before giving up. Pass None to wait
        indefinitely.

    Returns
    -------
    VariableServer
        A VariableServer connected to the sim matching the specified
        parameters.

    Raises
    ------
    socket.timeout
        If a timeout occurs.
    """
    clock = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", 9265))
    sock.setsockopt(
        socket.IPPROTO_IP,
        socket.IP_ADD_MEMBERSHIP,
        struct.pack("=4sl", socket.inet_aton("224.3.14.15"), socket.INADDR_ANY),
    )
    file_interface = sock.makefile()

    def candidate_matches(candidate: list[str]) -> bool:
        for parameter, candidate_parameter in zip(
            [host, port, user, pid, sim_directory, s_main, input_file, version, tag],
            candidate,
        ):
            if parameter is not None and str(parameter) != candidate_parameter:
                return False
        return True

    # the socket will clean itself up when it's garbage-collected
    while True:
        if timeout is not None:
            timeout -= time.time() - clock
            if timeout < 0:
                raise socket.timeout
            clock = time.time()
            sock.settimeout(timeout)

        # 0: host
        # 1: port
        # 2: user
        # 3: pid
        # 4: SIM_*
        # 5: S_main*
        # 6: RUN_*
        # 7: version
        # 8: tag
        candidate = file_interface.readline().split("\t")[:9]

        if not str(sim_directory).startswith("/") and len(candidate) > 4:
            candidate[4] = os.path.basename(candidate[4])

        if candidate_matches(candidate):
            return VariableServer(candidate[0], candidate[1])


def _parse_value(text: str) -> tuple[str, str | None]:
    """
    Parse a variable server value with optional units.

    Parameters
    ----------
    text : str
        The variable server text.

    Returns
    -------
    str, str (or None)
        A tuple containing:
            - The value.
            - The units, which may be None.
    """
    match = re.match(r"(?P<value>.*)(?: {(?P<units>.*)})", text)
    if match:
        return match.group("value"), match.group("units")
    return text, None


def _assert_message_type(message: Message, indicator: int) -> None:
    """
    Raise an error if the message indicator does not match the expected
    indicator.

    Parameters
    ----------
    message : Message
        The message to test.
    indicator : Message.Indicator
        The expected indicator.

    Raises
    ------
    UnexpectedMessageError
        If the message indicator does not match the expected indicator.
    """
    if message.indicator != indicator:
        raise UnexpectedMessageError(indicator, message.indicator)


def _assert_units_conversion(name: str, expected_units: str | None, actual_units: str | None) -> None:
    """
    Raise an error if the actual units do not match the expected units.

    Parameters
    ----------
    name : str
        The name of the variable being tested.
    expected_units : str
        The expected units.
    actual_units : str
        The actual units.

    Raises
    ------
    UnitsConversionError
        If the actual units do not match the expected units.
    """
    if expected_units != actual_units and expected_units != "xx":
        raise UnitsConversionError(name, expected_units)


def _assert_value_count(expected: int, actual: int) -> None:
    """
    Raise an error if actual does not match expected.

    Parameters
    ----------
    expected : any
        The expected value.
    actual : any
        The actual value.

    Raises
    ------
    ValueCountError
        If actual does not match expected.
    """
    if expected != actual:
        raise ValueCountError(expected, actual)


if __name__ == "__main__":
    import doctest

    doctest.testmod()
