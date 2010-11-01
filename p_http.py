#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2010-10-27
@author: shell.xu
'''
from __future__ import with_statement
import os
import sys
import socket
import traceback
from contextlib import contextmanager
import eventlet
import eventlet.pools
import pyweb
import socks

spawn = eventlet.greenthread.spawn

class ProxyRequest(pyweb.HttpRequest):

    @classmethod
    def make_request(cls, request, self = None):
        if self is None: self = cls(None)
        self = pyweb.HttpRequest.make_request(request.url, self)
        self.request, self.header = request, request.header
        self.verb, self.version = request.verb, request.version
        self.proc_header()
        return self

    def proc_header(self):
        self.connection = \
            self.get_header('proxy-connection', 'close') == 'keep-alive'
        del_keys = [i for i in self.header.keys() if i.startswith('proxy-')]
        for k in del_keys: del self.header[k]

    def make_response(self, code = 200):
        response = ProxyResponse(self, code)
        response.connection = self.connection
        return response

class ProxyResponse(pyweb.HttpResponse):

    def __init__(self, request, code):
        super(ProxyResponse, self).__init__(request, code)
        self.connection, self.trans_len = False, [0, 0]
        self.src_sock = request.request.sock

    def send_header(self):
        if self.header_sended: return
        self.request.responsed = True
        self.src_sock.sendall(self.make_header())
        self.header_sended = True

    def recv_body(self, hasbody = False):
        self.send_header()
        super(ProxyResponse, self).recv_body(hasbody)

    def body_len(self): return self.trans_len[1]
    def append_body(self, data):
        self.trans_len[1] += len(data)
        self.send_body(data)
    def end_body(self):
        if self.chunk_mode: self.src_sock.sendall('0\r\n\r\n')
        
    def send_body(self, data):
        if not self.chunk_mode: self.src_sock.sendall(data)
        else: self.src_sock.sendall('%x\r\n%s\r\n' %(len(data), data))

class ProxyBase(object):
    VERB_SOCKS = ['CONNECT', ]

    def __call__(self, request):
        if request.verb in self.VERB_SOCKS:
            if not hasattr(self, 'do_socks'):
                raise pyweb.MethodNotAllowedError()
            return self.do_socks(request)
        else: return self.do_http(request)

class ProxyDirect(ProxyBase):
    name = 'direct'

    @contextmanager
    def item(self):
        sock = pyweb.EventletClient()
        try: yield sock
        finally: sock.close()
    def connect(self, sock, sockaddr): sock.connect(sockaddr[0], sockaddr[1])

    def do_socks(self, request):
        response = request.make_response()
        hostname, sp, port = request.hostname.partition(':')
        if port: port = int(port)
        else: port = 80
        with self.item() as sock:
            try: self.connect(sock, (hostname, port))
            except (EOFError, socket.error): raise pyweb.BadGatewayError()
            response.send_header()
            request.timeout.cancel()
            th = spawn(self.trans_loop, request.sock, sock)
            self.trans_loop(sock, request.sock)
            th.wait()
        response.body_sended, response.connection = True, False
        return response
    def trans_loop(self, s1, s2):
        try:
            while True:
                d = s1.recv_once()
                s2.sendall(d)
        # TODO: just ignore EOFError, BreakPipe, socket.error, logging others
        except: pass

    def do_http(self, request):
        request.recv_body()
        preq = ProxyRequest.make_request(request)
        response = pyweb.http_client(preq, sock_factory = self)
        response.body_sended = True
        return response

class ForwardRequest(ProxyRequest):

    @classmethod
    def make_request(cls, request, self = None):
        if self is None: self = cls(None)
        self = pyweb.HttpRequest.make_request(request.url, self)
        self.request, self.header = request, request.header
        self.verb, self.url, self.version = \
            request.verb, request.url, request.version
        self.proc_header()
        return self

class ProxyForward(ProxyDirect):
    name = 'forward'

    def __init__(self, hostname, port, max_size = 20):
        self.hostname, self.port = hostname, port
        self.pool = eventlet.pools.TokenPool(max_size = max_size)

    @contextmanager
    def item(self):
        with self.pool.item():
            sock = pyweb.EventletClient()
            sock.connect(self.hostname, self.port)
            try: yield sock
            finally: sock.close()
    def connect(self, sock, sockaddr): pass

    def do_socks(self, request):
        response = request.make_response()
        with self.item() as sock:
            sock.sendall(request.make_header() + "".join(request.content))
            res_header = sock.recv_until()
            request.sock.sendall(res_header + '\r\n\r\n')
            response.header_sended = True

            request.timeout.cancel()
            th = spawn(self.trans_loop, request.sock, sock)
            self.trans_loop(sock, request.sock)
            th.wait()
        response.body_sended, response.connection = True, False
        return response

    def do_http(self, request):
        request.recv_body()
        preq = ForwardRequest.make_request(request)
        response = pyweb.http_client(preq, sock_factory = self)
        response.body_sended = True
        return response

class ProxySocks(ProxyDirect):
    name = 'socks'

    def __init__(self, hostname, port, max_size = 20):
        self.hostname, self.port = hostname, port
        self.pool = eventlet.pools.TokenPool(max_size = max_size)

    @contextmanager
    def item(self):
        with self.pool.item():
            sock = socks.SocksClient()
            sock.connect(self.hostname, self.port)
            try: yield sock
            finally: sock.close()
    def connect(self, sock, sockaddr):
        sock.proxy_connect(sockaddr[0], sockaddr[1])
