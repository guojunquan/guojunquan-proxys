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

class ProxyRequest(p_http.ProxyRequest):

    def make_request(self, request):
        super(ProxyRequest, self).make_request(request)
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
        sock = pyweb.EventletClient()
        try:
            try: sock.connect(self.hostname, self.port)
            except (EOFError, socket.error): raise pyweb.BadGatewayError()
            request.timeout.cancel()

            sock.sendall(request.make_header() + "".join(request.content))
            response = request.make_response()
            res_header = sock.recv_until()
            response.sock.sendall(res_header + '\r\n\r\n')
            response.header_sended = True

            request.sock.server.pool.spawn_n(self.trans_loop, request.sock, sock)
            self.trans_loop(sock, request.sock)
        finally: sock.close()
        return response

    def make_client(self): return ProxyClient(self.hostname, self.port)
