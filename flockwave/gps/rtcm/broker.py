"""RTCM packet broker that collects RTCM packets from multiple producers
and dispatches them to consumers.
"""

from __future__ import absolute_import, print_function

from abc import ABCMeta, abstractmethod, abstractproperty
from collections import defaultdict
from future.utils import iteritems, itervalues, with_metaclass
from select import select
from time import time
from .packets import RTCMV3Packet
from .parser import RTCMV3Parser

import errno
import socket


__all__ = ("RTCMPacketBroker", "RTCMPacketProducer", "RTCMPacketConsumer")


class NoMorePackets(RuntimeError):
    """Error thrown by an RTCMPacketProducer_ when it cannot produce packets
    any more.
    """

    pass


class SocketBasedInterruptionHelper(object):
    """Object that encapsulates a pair of UDP sockets: a server socket and
    a client socket. These are connected to each other and are used to
    implement interruption support in the main loop of an RTCM packet broker.

    When the main loop is listening for new data on the RTCM packet producers,
    it may happen that a new producer is added to the broker from a different
    thread. In that case, the broker must break out of the ``select()`` call
    that blocks until new data becomes available on the RTCM packet producers
    in order to notice the new producer. Unfortunately, there is no standard
    way to break out of a ``select()`` call, so we add a dummy UDP socket
    (the server socket of this object) to the ``select()`` call. Whenever we
    need to interrupt the ``select()`` call in the broker, we write a dummy
    byte to the client UDP socket, which unblocks the ``select()`` call. Then
    we drain the server socket and then let the broker start the next iteration
    of the loop.
    """

    def __init__(self):
        self._server_socket, self._client_socket = self._prepare_sockets()

    def _prepare_sockets(self):
        """Prepares the input and output pipes."""
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.setblocking(0)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(('127.0.0.1', 0))
        server_address = server.getsockname()

        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        client.connect(server_address)

        return server, client

    def close(self):
        self._client_socket.close()
        self._server_socket.close()

    def drain(self):
        """Drains the server socket by reading everything that is currently
        available.
        """
        while True:
            try:
                self._server_socket.recv(1)
            except socket.error as ex:
                if ex.errno == errno.EAGAIN:
                    # The socket is drained
                    return
                else:
                    raise
            except OSError as ex:
                if ex.errno == errno.EAGAIN:
                    # The socket is drained
                    return
                else:
                    raise

    def fileno(self):
        return self._server_socket.fileno()

    def interrupt(self):
        self._client_socket.send(b'x')


class RTCMPacketProducer(object):
    """Base class for objects backed by file descriptors that produce RTCM
    packets.

    The producer closes itself automatically when it detects that the
    underlying file descriptor is most likely closed. This is detected by
    the fact that ``read()`` returns no data twice in a row, which is likely
    to be okay if you call ``produce()`` only when you know that the file
    descriptor is ready for reading.

    For ordinary files, this approach is okay because they always seem to
    be ready for reading, and they start returning no data from ``read()``
    when you reach the end of file. For sockets, this approach works because
    they become readable (and stay that way forever) when they are closed
    but of course return no data.
    """

    def __init__(self, fp, parser_factory=RTCMV3Parser, name=None):
        """Constructor.

        :param fp: a file-like object that has a ``fileno()`` method and is in
            non-blocking mode.
        :type fp: int or file-like
        """
        self.fp = fp
        self.parser = parser_factory()
        self.name = name or "<{0.__class__.__name__}(fp={0.fp!r})>"\
            .format(self)
        self._maybe_closed = False

    def close(self):
        """Closes the file-like object associated with the producer."""
        self.fp.close()

    def fileno(self):
        """Returns the integer file descriptor of the packet producer. This
        can be used in ``select()`` calls that affect the producer.
        """
        return self.fp.fileno()

    def produce(self):
        """Feeds the available bytes on the file-like object to an RTCM packet
        parser.

        It is guaranteed that this function is called by the broker only when
        the file-like object is ready to be read from.

        :return: the packets that were produced by the parser from the data
        :raise NoMorePackets: if the producer is not able to produce more
            packets (typically because the file-like object is closed)
        """
        data = self.fp.read()
        if data:
            self._maybe_closed = False
            return self.parser.feed(data)
        else:
            if self._maybe_closed:
                raise NoMorePackets
            else:
                self._maybe_closed = True
                return []


class RTCMPacketConsumer(with_metaclass(ABCMeta, object)):
    """Base class for objects that consume RTCM packets of specific types."""

    @abstractproperty
    def accepts(self):
        """Returns an iterable of classes that this packet consumer is
        interested in.
        """
        raise NotImplementedError

    @abstractmethod
    def __call__(self, packet, producer):
        """Handles the given RTCM packet.

        :param packet: the packet to handle
        :type packet: RTCMV3Packet
        :param producer: the packet producer that produced the packet
        :type producer: RTCMPacketProducer
        :return: whether the packet was handled
        :rtype: bool
        """
        raise NotImplementedError


class ProducerInfo(object):
    def __init__(self, producer, autoclose=False, timeout=None):
        self.producer = producer
        self.autoclose = autoclose
        self.timeout = timeout
        self._last_packet_time = time()

    @property
    def next_packet_time(self):
        if self.timeout is None:
            return None
        else:
            return self._last_packet_time + self.timeout

    def touch(self):
        self._last_packet_time = time()


class RTCMPacketBroker(object):
    """RTCM packet broker object that collects RTCM packets from multiple
    sources (typically NTRIP streams) and dispatches them to interested
    parties.
    """

    def __init__(self):
        """Constructor."""
        self._producers = {}
        self._producers_changed = False
        self._consumers = defaultdict(set)
        self._closed = False
        self._interruption_helper = SocketBasedInterruptionHelper()

    def __del__(self):
        if not getattr(self, "_closed", True):
            self.close()

    def _assert_not_closed(self):
        """Asserts that the broker is not closed yet.

        :throws ValueError: if the broker is closed
        """
        if self._closed:
            raise ValueError("broker is already closed")

    def _calculate_time_to_next_packet(self):
        next_time = None
        for producer_info in itervalues(self._producers):
            if producer_info.next_packet_time is None:
                continue
            if next_time is None:
                next_time = producer_info.next_packet_time
            else:
                next_time = min(producer_info.next_packet_time, next_time)
        if next_time is None:
            return None
        else:
            return max(0, next_time - time())

    def _handle_packet(self, packet, producer):
        """Dispatches a given RTCM packet to the interested consumers."""
        for cls in self._consumers:
            if isinstance(packet, cls):
                for consumer in self._consumers[cls]:
                    consumer(packet, producer)

    def add_consumer(self, consumer):
        """Registers the given RTCM packet consumer in the broker.

        :param consumer: the consumer that will be called whenever a packet
            relevant to the consumer is received.
        :type consumer: RTCMPacketConsumer
        """
        accepts = getattr(consumer, "accepts", [RTCMV3Packet])
        for cls in accepts:
            self._consumers[cls].add(consumer)

    def add_producer(self, producer, autoclose=False, timeout=None):
        """Registers the given RTCM packet producer in the broker.

        :param producer: the producer to register
        :type producer: RTCMPacketProducer
        :param close: whether to close the producer automatically when
            the broker is closed
        :type close: bool
        """
        fileno = producer.fileno()

        self._producers[fileno] = ProducerInfo(
            producer=producer, autoclose=autoclose, timeout=timeout)
        self._producers_changed = True

        self.interrupt()

    def close(self):
        """Closes the broker and all the producers that were registered with
        ``autoclose=True``.
        """
        self._assert_not_closed()
        for producer_info in itervalues(self._producers):
            if producer_info.autoclose:
                producer_info.producer.close()
        self._closed = True
        self.interrupt()
        self._interruption_helper.close()

    def handle_data_on_fds(self, fds):
        """Handles any incoming data on the given file descriptors. Note that
        this function *will* block on a given file descriptor if there is no
        incoming data and the file descriptor is in blocking mode. It is best
        to use this function in conjunction with ``select()``; see the
        ``loop()`` function for an example.
        """
        for fd in fds:
            self._handle_data_on_fd(fd)

    def _handle_data_on_fd(self, fd):
        """Handles any incoming data on the given file descriptor. Note that
        this function *will* block on the file descriptor if there is no
        incoming data and the file descriptor is in blocking mode. It is best
        to use this function in conjunction with ``select()``; see the
        ``loop()`` function for an example.
        """
        producer_info = self._producers.get(fd)
        if producer_info is None:
            return

        producer_info.touch()

        producer = producer_info.producer
        try:
            for packet in producer.produce():
                self._handle_packet(packet, producer)
        except NoMorePackets:
            producer.close()
            self.remove_producer(producer)

    def interrupt(self):
        """Causes the broker to interrupt the current ``select()`` call and
        start the next iteration. Usually not needed from the outside.
        """
        self._interruption_helper.interrupt()

    def loop(self):
        """Enters an infinite loop that waits for producers to produce
        packets and dispatches them to the appropriate consumers.

        Producers may not be added to the broker after it has entered the main
        loop; new producers will not be noticed.
        """
        self._assert_not_closed()

        all_fds = None
        self._interruption_helper.drain()

        while not self._closed:
            if all_fds is None or self._producers_changed:
                self._producers_changed = False
                all_fds = list(self._producers.keys()) + \
                    [self._interruption_helper]

            timeout = self._calculate_time_to_next_packet()
            if timeout is not None:
                fds, _, _ = select(all_fds, [], [], timeout)
            else:
                fds, _, _ = select(all_fds, [], [])

            if self._interruption_helper in fds:
                self._interruption_helper.drain()
                fds.remove(self._interruption_helper)

            self.handle_data_on_fds(fds)
            self.handle_timeouts()

    def handle_timeouts(self):
        """Iterates over all producers and checks whether any of them has
        timed out (i.e. hasn't produced a packet in a while and has an
        associated timeout). Removes produces that have timed out from
        the broker. This function should be called periodically if you are
        not running the broker via ``loop()``.
        """
        now = time()
        timed_out = set()
        for key, producer_info in iteritems(self._producers):
            next_time = producer_info.next_packet_time
            if next_time is not None and next_time < now:
                timed_out.add(producer_info.producer)

        for producer in timed_out:
            producer.close()
            self.remove_producer(producer)

    def remove_consumer(self, consumer):
        """Removes the given RTCM packet consumer from the broker.

        :param consumer: the consumer to remove
        :type consumer: RTCMPacketConsumer
        """
        for cls, consumers in iteritems(self._consumers):
            consumers.discard(consumer)

    def remove_producer(self, producer):
        """Removes the given RTCM packet producer from the broker.

        :param producer: the producer to remove
        :type producer: RTCMPacketProducer
        """
        keys_to_delete = [key for key, value in iteritems(self._producers)
                          if value.producer is producer]
        for key in keys_to_delete:
            del self._producers[key]

        self._producers_changed = True
        self.interrupt()
