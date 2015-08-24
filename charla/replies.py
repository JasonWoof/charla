"""Internet Relay Chat Protocol replies

Extended version of circuits.protocols.irc.replies
"""


from circuits.protocols.irc.replies import _M
from circuits.protocols.irc.replies import *  # noqa


def MODE(target, modes, params=None, prefix=None):
    if params is None:
        return Message(u"MODE", target, modes, prefix=prefix)
    return Message(u"MODE", target, modes, u" ".join(params), prefix=prefix)


def JOIN(name, prefix=None):
    return Message(u"JOIN", name, prefix=prefix)


def TOPIC(channel, topic, prefix=None):
    return Message(u"TOPIC", channel, topic, prefix=prefix)


def RPL_CREATED(date):
    return _M(u"003", u"This server was created {0}".format(date))


def RPL_ISUPPORT(features):
    return _M(u"005", *(features + (u"are supported by this server",)))


def RPL_UMODEIS(modes):
    return _M(u"221", modes)


def RPL_CHANNELMODEIS(channel, mode, params=None):
    if params is None:
        return _M(u"324", channel, mode)
    return _M(u"324", channel, mode, params)


def RPL_VERSION(name, version, hostname, url):
    return _M(u"351", name, version, hostname, url)


def RPL_TOPIC(channel, topic):
    return _M(u"332", channel, topic)


def ERR_USERNOTINCHANNEL(nick, channel):
    return _M(u"441", nick, channel, u"They aren't on that channel")


def ERR_NEEDMOREPARAMS(command):
    return _M(u"461", command, u"Need more parameters")


def ERR_CHANOPRIVSNEEDED(channel):
    return _M(u"482", channel, u"You're not channel operator")


def ERR_UNKNOWNMODE(mode, channel=None):
    if channel is None:
        return _M(u"472", mode, u"is unknown mode char to me")
    return _M(u"472", mode, u"is unknown mode char to me for channel {1}".format(channel))


def ERR_ERRONEUSNICKNAME(nick):
    return _M(u"432", nick, u"Erroneous nickname")


def ERR_TOOMANYCHANNELS(channel):
    return _M(u"405", channel, u"You have joined too many channels")


def ERR_NONICKNAMEGIVEN():
    return _M(u"431", "No nickname given")


def RPL_WHOISUSER(nick, user, host, realname):
    return _M(u"311", nick, user, host, u"*", realname)


def RPL_WHOISCHANNELS(nick, channels):
    return _M(u"319", nick, " ".join(channels))


def RPL_WHOISSERVER(nick, server, server_info):
    return _M(u"312", nick, server, server_info)


def RPL_ENDOFWHOIS(nick):
    return _M(u"318", nick, u"End of WHOIS list")


def RPL_MOTDSTART(server):
    return _M(u"375", u"- {0} Message of the day -".format(server))


def RPL_MOTD(text):
    return _M(u"372", u"- {0}".format(text))


def RPL_ENDOFMOTD():
    return _M(u"376", u"End of MOTD command")
