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
import logging
import traceback
from contextlib import contextmanager
from greenlet import greenlet
import pyweb
import socks

socks_timeout = 1200

class ProxyRequest(pyweb.HttpRequest):

    @classmethod
    def make_request(cls, request, self = None):
        if self is None: self = cls(None)
        self = pyweb.HttpRequest.make_request(request.url, self)
        self.request, self.header = request, request.header
        self.verb, self.version = request.verb, request.version
        self.content, self.trans_len = request.content, [0, 0]
        self.proc_client_header()
        return self

    def proc_client_header(self):
        self.connection = \
            self.get_header('proxy-connection', 'close') == 'keep-alive'
        self.header = dict([(k, v) for k, v in self.header.items()
                            if not k.startswith('proxy-')])

    def make_response(self, code = 200):
        response = ProxyResponse(self, code)
        response.connection = self.connection
        return response

class ProxyResponse(pyweb.HttpResponse):

    def __init__(self, request, code):
        super(ProxyResponse, self).__init__(request, code)
        self.connection, self.src_sock = False, request.request.sock

    def send_header(self):
        if self.header_sended: return
        self.request.responsed = True
        if self.get_header('connection', '') == 'close':
            self.connection = False
        self.src_sock.sendall(self.make_header())
        self.header_sended = True

    def recv_body(self, hasbody = False):
        self.send_header()
        super(ProxyResponse, self).recv_body(hasbody)

    def body_len(self): return self.request.trans_len[1]
    def append_body(self, data):
        self.request.trans_len[1] += len(data)
        self.send_body(data)
    def end_body(self):
        if self.chunk_mode: self.send_body('')
        
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
        sock = pyweb.EpollSocket()
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
            request.trans_len = [0, 0]
            pyweb.bus.unset_timeout(request.timeout)
            request.timeout = pyweb.bus.set_timeout(socks_timeout,
                                                    pyweb.TimeoutError)
            gr = greenlet(self.trans_loop)
            pyweb.bus.next_job(gr, request.sock, sock, request.trans_len, 0)
            self.trans_loop(sock, request.sock, request.trans_len, 1)
            while not gr.dead: pyweb.bus.schedule()
        response.body_sended, response.connection = True, False
        return response
    def trans_loop(self, s1, s2, counter, num):
        try:
            for d in s1.datas():
                counter[num] += len(d)
                s2.sendall(d)
        except EOFError, socket.error: pass
        except KeyboardInterrupt: raise
        except: logging.error(''.join(traceback.format_exc()))

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
        self.proc_client_header()
        return self

class ProxyForward(ProxyDirect):
    name = 'forward'

    def __init__(self, hostname, port, max_size = 20):
        self.hostname, self.port = hostname, port
        self.pool = pyweb.TokenPool(max_size)

    @contextmanager
    def item(self):
        with self.pool.item():
            sock = pyweb.EpollSocket()
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
            request.trans_len = [0, 0]

            pyweb.bus.unset_timeout(request.timeout)
            request.timeout = pyweb.bus.set_timeout(socks_timeout,
                                                    pyweb.TimeoutError)
            gr = greenlet(self.trans_loop)
            pyweb.bus.next_job(gr, request.sock, sock, request.trans_len, 0)
            self.trans_loop(sock, request.sock, request.trans_len, 1)
            while not gr.dead: pyweb.bus.schedule()
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
        self.pool = pyweb.TokenPool(max_size)

    @contextmanager
    def item(self):
        with self.pool.item():
            sock = socks.SocksClient()
            sock.connect(self.hostname, self.port)
            try: yield sock
            finally: sock.close()
    def connect(self, sock, sockaddr):
        sock.proxy_connect(sockaddr[0], sockaddr[1])
