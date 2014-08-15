#!/usr/bin/env python


"""IRC Daemon"""


import logging
from logging import getLogger

from time import time
from sys import stderr
from itertools import chain
from operator import attrgetter
from collections import defaultdict
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser


from circuits import handler, Component, Debugger

from circuits.net.sockets import TCPServer
from circuits.net.events import close, write

from circuits.protocols.irc import reply, response, IRC, Message

from circuits.protocols.irc.replies import (
    ERR_NOMOTD, ERR_NOSUCHNICK, ERR_NOSUCHCHANNEL, ERR_UNKNOWNCOMMAND,
    RPL_WELCOME, RPL_YOURHOST, RPL_WHOREPLY, RPL_ENDOFWHO, RPL_NOTOPIC,
    RPL_NAMEREPLY, RPL_ENDOFNAMES,
    ERR_NICKNAMEINUSE,
)


from models import User, Channel


__version__ = "0.0.1"


def parse_args():
    parser = ArgumentParser(
        description=__doc__,
        formatter_class=ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "-v", "--version",
        action="version",
        version="%(prog)s {version}".format(version=__version__)
    )

    parser.add_argument(
        "-b", "--bind",
        action="store", type=str,
        default="0.0.0.0:6667", dest="bind",
        help="Bind to address:[port]"
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        default=False, dest="debug",
        help="Enable debug mode"
    )

    return parser.parse_args()


class Server(Component):

    channel = "server"

    network = "Test"
    host = "localhost"
    version = "ircd v{0:s}".format(__version__)

    def init(self, args, logger=None):
        self.args = args
        self.logger = logger or getLogger(__name__)

        self.buffers = defaultdict(bytes)

        self.nicks = {}
        self.users = {}
        self.channels = {}

        Debugger(events=args.debug, logger=self.logger).register(self)

        if ":" in args.bind:
            address, port = args.bind.split(":")
            port = int(port)
        else:
            address, port = args.bind, 6667

        bind = (address, port)

        self.transport = TCPServer(
            bind,
            channel=self.channel
        ).register(self)

        self.protocol = IRC(
            channel=self.channel,
            getBuffer=self.buffers.__getitem__,
            updateBuffer=self.buffers.__setitem__
        ).register(self)

    def _notify(self, users, message, exclude=None):
        for user in users:
            if exclude is not None and user is exclude:
                continue
            self.fire(reply(user.sock, message))

    def read(self, sock, data):
        user = self.users[sock]
        host, port = user.host, user.port

        self.logger.info(
            "I: [{0:s}:{1:d}] {2:s}".format(host, port, repr(data))
        )

    def write(self, sock, data):
        if sock in self.users:
            user = self.users[sock]
        else:
            user = User(sock, "", 0)

        host, port = user.host, user.port

        self.logger.info(
            "O: [{0:s}:{1:d}] {2:s}".format(host, port, repr(data))
        )

    def ready(self, server, bind):
        stderr.write(
            "ircd v{0:s} ready! Listening on: {1:s}\n".format(
                __version__, "{0:s}:{1:d}".format(*bind)
            )
        )

    def connect(self, sock, host, port):
        self.users[sock] = User(sock, host, port)

        self.logger.info("C: [{0:s}:{1:d}]".format(host, port))

    def disconnect(self, sock):
        if sock not in self.users:
            return

        user = self.users[sock]

        self.logger.info("D: [{0:s}:{1:d}]".format(user.host, user.port))

        nick = user.nick
        user, host = user.userinfo.user, user.userinfo.host

        yield self.call(
            response.create("quit", sock, (nick, user, host), "Leavling")
        )

        del self.users[sock]

        if nick in self.nicks:
            del self.nicks[nick]

    def quit(self, sock, source, reason="Leaving"):
        user = self.users[sock]

        channels = [self.channels[channel] for channel in user.channels]
        for channel in channels:
            channel.users.remove(user)
            if not channel.users:
                del self.channels[channel.name]

        users = chain(*map(attrgetter("users"), channels))

        self.fire(close(sock))

        self._notify(
            users,
            Message("QUIT", reason, prefix=user.prefix), user
        )

    def nick(self, sock, source, nick):
        user = self.users[sock]

        if nick in self.nicks:
            return self.fire(reply(sock, ERR_NICKNAMEINUSE(nick)))

        if not user.registered and user.userinfo:
            user.registered = True
            self.fire(response.create("signon", sock, user))

        user.nick = nick
        self.nicks[nick] = user

    def user(self, sock, source, nick, user, host, name):
        _user = self.users[sock]

        _user.userinfo.user = user
        _user.userinfo.host = host
        _user.userinfo.name = name

        if not _user.registered and _user.nick:
            _user.registered = True
            self.fire(response.create("signon", sock, source))

    def signon(self, sock, source):
        user = self.users[sock]
        if user.signon:
            return

        user.signon = time()

        self.fire(reply(sock, RPL_WELCOME(self.network)))
        self.fire(reply(sock, RPL_YOURHOST(self.host, self.version)))
        self.fire(reply(sock, ERR_NOMOTD()))

        # Force users to join #circuits
        self.fire(response.create("join", sock, source, "#circuits"))

    def join(self, sock, source, name):
        user = self.users[sock]

        if name not in self.channels:
            channel = self.channels[name] = Channel(name)
        else:
            channel = self.channels[name]

        if user in channel.users:
            return

        user.channels.append(name)
        channel.users.append(user)

        self._notify(
            channel.users,
            Message("JOIN", name, prefix=user.prefix)
        )

        self.fire(reply(sock, RPL_NOTOPIC(name)))
        self.fire(reply(sock, RPL_NAMEREPLY(channel)))
        self.fire(reply(sock, RPL_ENDOFNAMES()))

    def part(self, sock, source, name, reason="Leaving"):
        user = self.users[sock]

        channel = self.channels[name]

        self._notify(
            channel.users,
            Message("PART", name, reason, prefix=user.prefix)
        )

        user.channels.remove(name)
        channel.users.remove(user)

        if not channel.users:
            del self.channels[name]

    def privmsg(self, sock, source, target, message):
        user = self.users[sock]

        if target.startswith("#"):
            if target not in self.channels:
                return self.fire(reply(sock, ERR_NOSUCHCHANNEL(target)))

            channel = self.channels[target]

            self._notify(
                channel.users,
                Message("PRIVMSG", target, message, prefix=user.prefix),
                user
            )
        else:
            if target not in self.nicks:
                return self.fire(reply(sock, ERR_NOSUCHNICK(target)))

            self.fire(
                reply(
                    self.nicks[target].sock,
                    Message("PRIVMSG", target, message, prefix=user.prefix)
                )
            )

    def who(self, sock, source, mask):
        if mask.startswith("#"):
            if mask not in self.channels:
                return self.fire(reply(sock, ERR_NOSUCHCHANNEL(mask)))

            channel = self.channels[mask]

            for user in channel.users:
                self.fire(reply(sock, RPL_WHOREPLY(user, mask, self.host)))
            self.fire(reply(sock, RPL_ENDOFWHO(mask)))
        else:
            if mask not in self.nicks:
                return self.fire(reply(sock, ERR_NOSUCHNICK(mask)))

            user = self.nicks[mask]

            self.fire(reply(sock, RPL_WHOREPLY(user, mask, self.host)))
            self.fire(reply(sock, RPL_ENDOFWHO(mask)))

    def ping(self, event, sock, source, server):
        event.stop()
        self.fire(reply(sock, Message("PONG", server)))

    def reply(self, target, message):
        user = self.users[target]

        if message.add_nick:
            message.args.insert(0, user.nick or "")

        if message.prefix is None:
            message.prefix = self.host

        self.fire(write(target, bytes(message)))

    @property
    def commands(self):
        exclude = {"ready", "connect", "disconnect", "read", "write"}
        return list(set(self.events()) - exclude)

    @handler()
    def _on_event(self, event, *args, **kwargs):
        if event.name.endswith("_done"):
            return

        if isinstance(event, response):
            if event.name not in self.commands:
                event.stop()
                self.fire(reply(args[0], ERR_UNKNOWNCOMMAND(event.name)))


def main():
    args = parse_args()

    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=stderr,
        level=logging.DEBUG if args.debug else logging.INFO
    )

    logger = getLogger(__name__)

    Server(args, logger=logger).run()


if __name__ == "__main__":
    main()
