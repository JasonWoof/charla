from socket import gethostbyaddr


from circuits import handler, task
from circuits.protocols.irc import reply, Message


from ..events import signon
from ..plugin import BasePlugin
from ..models import User, UserInfo


def check_host(sock):
    host, _ = sock.getpeername()
    return gethostbyaddr(host)[0]


class CheckHostPlugin(BasePlugin):
    """Check Host Plugin"""

    __version__ = "0.0.1"
    __author__ = "James Mills, prologic at shortcircuit dot net dot au"

    def init(self, *args, **kwargs):
        super(CheckHostPlugin, self).init(*args, **kwargs)

        self.pending = {}

    def task_complete(self, e, value):
        _, sock = e.args
        del self.pending[sock]

        self.fire(reply(sock, Message("NOTICE", "*", "*** Found your hostname")))

        user = User.objects.filter(sock=sock).first()

        if user.userinfo is None:
            userinfo = UserInfo()
            userinfo.save()

            user.userinfo = userinfo
            user.save()

        user.userinfo.host = value
        user.userinfo.save()

        if user.registered:
            return signon(sock, user.source)

    def connect(self, sock, host, port):
        self.pending[sock] = True
        self.fire(reply(sock, Message("NOTICE", "*", "*** Looking up your hostname...")))

        e = task(check_host, sock)
        e.complete = True
        e.complete_channels = ("server",)

        self.fire(e, "threadpool")

    @handler("signon", priority=1.0)
    def signon(self, event, sock, source):
        if self.pending.get(sock, False):
            event.stop()
