#!/usr/bin/make -f

PROJ_NAME	= pywebproxy
PYTHON 		= /usr/bin/python

INSTALL		= /usr/bin/install
INSTALL_BIN	= $(INSTALL) -m 755
INSTALL_DATA	= $(INSTALL) -m 644
INSTALL_OBJS	= cgi.py http_hoh.py p_gfw.py p_http.py socks.py run

prefix		= /usr
ETCDIR		= $(DESTDIR)/etc/pywebproxy
SHAREDIR	= $(DESTDIR)$(prefix)/share/pywebproxy
LOGDIR		= $(DESTDIR)/var/log/pywebproxy

all: build

build-deb: build
	dpkg-buildpackage -rfakeroot

build:

clean:
	rm -f *.pyc *.pyo
	rm -rf build
	rm -f python-build-stamp*
	rm -rf debian/python-$(PROJ_NAME)
	rm -f debian/python-$(PROJ_NAME)*
	rm -f debian/pycompat
	rm -rf debian/python-module-stampdir

install-bin: build
	$(INSTALL_BIN) -d $(SHAREDIR)
	for file in $(INSTALL_OBJS);\
	do \
		$(INSTALL_BIN) $$file $(SHAREDIR); \
	done;

install:  install-bin
	$(INSTALL_BIN) -d $(ETCDIR)
	$(INSTALL_DATA) gfw $(ETCDIR)/gfw
	$(INSTALL_BIN) -d $(LOGDIR)
