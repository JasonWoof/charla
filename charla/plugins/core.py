import re
from itertools import chain
from operator import attrgetter


from circuits.protocols.irc import joinprefix, Message


from ..events import signon
from ..plugin import BasePlugin
from ..models import User, UserInfo
from ..commands import BaseCommands
from ..replies import ERR_ERRONEUSNICKNAME, ERR_NICKNAMEINUSE


VALID_NICK_REGEX = re.compile(r"^[][\`_^{|}A-Za-z][][\`_^{|}A-Za-z0-9-]*$")


class Commands(BaseCommands):

    def quit(self, sock, source, reason=u"Leaving"):
        user = User.objects.filter(sock=sock).first()

        for channel in user.channels:
            channel.users.remove(user)

            if not channel.users:
                channel.delete()

        users = chain(*map(attrgetter("users"), user.channels))

        self.disconnect(user)

        self.notify(users, Message(u"QUIT", reason, prefix=user.prefix), user)

    def nick(self, sock, source, nick):
        user = User.objects.filter(sock=sock).first()

        if not VALID_NICK_REGEX.match(nick):
            return ERR_ERRONEUSNICKNAME(nick)

        if User.objects.filter(nick=nick):
            return ERR_NICKNAMEINUSE(nick)

        prefix = user.prefix or joinprefix(*source)
        user.nick = nick
        user.save()

        if not user.registered and user.userinfo is not None:
            user.registered = True
            user.save()
            return signon(sock, user.source)

        users = chain(*map(attrgetter("users"), user.channels))

        self.notify(users, Message(u"NICK", nick, prefix=prefix))

    def user(self, sock, source, username, hostname, server, realname):
        _user = User.objects.filter(sock=sock).first()

        if _user.userinfo is None:
            userinfo = UserInfo(
                user=username, host=hostname, name=realname, server=server
            )
        else:
            userinfo = _user.userinfo
            userinfo.user = username
            userinfo.name = realname
            userinfo.server = server

        userinfo.save()

        _user.userinfo = userinfo
        _user.save()

        if not _user.registered and _user.nick:
            _user.registered = True
            _user.save()
            return signon(sock, _user.source)


class Core(BasePlugin):

    def init(self, *args, **kwargs):
        super(Core, self).init(*args, **kwargs)

        Commands(*args, **kwargs).register(self)
