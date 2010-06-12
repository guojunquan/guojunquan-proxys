INSTALL=install
OBJECTS=default_setting.pyo log.pyo server.pyo base.pyo http.pyo
ACTIONS=http_filter.pyo http_proxy.pyo http_cache.pyo http_hoh.pyo
ADDONS=lrucache.pyo socks.pyo

DESTDIR=
perfix=$(DESTDIR)/usr
BINDIR=$(perfix)/bin
LIBDIR=$(perfix)/lib/pyshared/python2.5/pywebproxy

%.pyo: %.py
	python -O -c "import $(basename $^)"

%.pyc: %.py
	python -c "import $(basename $^)"

all: build

build: $(OBJECTS) $(ACTIONS) $(ADDONS)

updatecgi:
	scp cgi.py shhawk:~/www/cgi-bin/test.py

downcgi:
	scp shhawk:~/www/cgi-bin/test.py cgi.py

#clean up
clean:
	rm -rf *.pyc *.pyo

test: build
	./pywebproxy test

install: build
	$(INSTALL) -d $(BINDIR)
	$(INSTALL) -m 755 pywebproxy $(BINDIR)
	$(INSTALL) -d $(LIBDIR)
	$(INSTALL) -m 644 -t $(LIBDIR) $(OBJECTS) $(ACTIONS) $(ADDONS)
