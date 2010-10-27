#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2010-10-27
@author: shell.xu
'''
from __future__ import with_statement
import os
import sys
import pyweb
import p_http

class ProxyRequest(p_http.HttpRequest):

    def make_request(self, request):
        super(ProxyRequest, self).make_request(request.url)
        self.request, self.header = request, request.header
        self.verb, self.url, self.version = \
            request.verb, request.url, request.version
        self.proc_header()

class ProxyClient(pyweb.HttpClient):
    RequestCls = ProxyRequest

    def __init__(self, hostname, port): self.hostname, self.port = hostname, port
    def make_sock(self, sockaddr):
        sock = pyweb.EventletClient()
        sock.connect(self.hostname, self.port)
        return sock

class ProxyForward(p_http.ProxyDirect):
    name = 'forward'

    def __init__(self, hostname, port): self.hostname, self.port = hostname, port

    def do_socks(self, request):
        pass

    def make_client(self): return ProxyClient(self.hostname, self.port)
