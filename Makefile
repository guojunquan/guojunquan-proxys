#!/usr/bin/make -f

PYTHON = /usr/bin/python

INSTALL		= /usr/bin/install
INSTALL_BIN	= $(INSTALL) -m 755
INSTALL_DATA	= $(INSTALL) -m 644
INSTALL_OBJS	= cgi.py http_hoh.py p_gfw.py p_hoh.py p_http.py socks.py

prefix		= /usr
BINDIR		= $(DESTDIR)$(prefix)/bin
ETCDIR		= $(DESTDIR)/etc/pywebproxy
INITDIR		= $(DESTDIR)/etc/init.d
SHAREDIR	= $(DESTDIR)$(prefix)/share

all: build

build:

clean:
	rm -f *.pyc *.pyo

install-bin: build
	for file in $(INSTALL_OBJS);\
	do \
		$(INSTALL_BIN) $$file $(SHAREDIR); \
	done;

install-init:
	$(INSTALL_BIN) -d $(INITDIR)
	$(INSTALL_DATA) debian/init.d $(INITDIR)/pywebproxy

install-etc:
	$(INSTALL_BIN) -d $(ETCDIR)
	$(INSTALL_DATA) gfw $(ETCDIR)/gfw

install: install-init install-etc install -bin

