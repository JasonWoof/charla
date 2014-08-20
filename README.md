charla
======

charla is [Spanish for chat][] and is an IRC Server and Daemon written in [Python][] using the [circuits][] Application Framework.

Installation and Usage
----------------------

From Source:

    $ hg clone https://bitbucket.org/circuits/charla
    $ cd charla
    $ ./server.py

From Source using [fig][] and [Docker][]:

    $ hg clone https://bitbucket.org/circuits/charla
    $ cd charla
    $ fig up

Using [Docker][]:

    $ docker run -d 6667:6667 prologic/charla

From PyPi (*ccoming soon*):

    $ pip install charla
    $ charla

  [Spanish for chat]: http://www.spanishcentral.com/translate/charla
  [Python]: http://python.org/
  [circuits]: http://circuitsframework.org/
  [fig]: http://fig.sh/
  [Docker]: http://docker.com/
