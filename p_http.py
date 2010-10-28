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
import eventlet
import pyweb
import socks

spawn = eventlet.greenthread.spawn

class ProxyRequest(pyweb.HttpRequest):

    def make_request(self, request):
        super(ProxyRequest, self).make_request(request.url)
        self.request, self.header = request, request.header
        self.verb, self.version = request.verb, request.version
        self.proc_header()

    def proc_header(self):
        if self.get_header('proxy-connection', 'close') == 'keep-alive':
            self.connection = True
        else: self.connection = False
        del_keys = [i for i in self.header.keys() if i.startswith('proxy-')]
        for k in del_keys: del self.header[k]

    def make_response(self, code = 200):
        response = ProxyResponse(self, code)
        response.connection = self.connection
        return response

class ProxyResponse(pyweb.HttpResponse):
    DEFAULT_HASBODY = True

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

class ProxyClient(pyweb.HttpClient):
    RequestCls = ProxyRequest

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
    DefaultClient = pyweb.EventletClient

    def sock_connect(self, sock, request):
        hostname, sp, port = request.hostname.partition(':')
        if port: port = int(port)
        else: port = 80
        sock.connect(hostname, port)

    def do_socks(self, request):
        response = request.make_response()
        sock = self.DefaultClient()
        try:
            try: self.sock_connect(sock, request)
            except (EOFError, socket.error): raise pyweb.BadGatewayError()
            response.send_header()
            request.timeout.cancel()
            th = spawn(self.trans_loop, request.sock, sock)
            self.trans_loop(sock, request.sock)
            th.wait()
        finally: sock.close()
        response.body_sended, response.connection = True, False
        return response
    def trans_loop(self, s1, s2):
        try:
            while True:
                d = s1.recv_once()
                s2.sendall(d)
        except EOFError, socket.error: pass
        print 'trans_loop end'

    def make_client(self): return ProxyClient()
    def do_http(self, request):
        request.recv_body()
        client = self.make_client()
        preq = client.make_request(request)
        response = client.handler(preq)
        response.body_sended = True
        return response

class ForwardRequest(ProxyRequest):

    def make_request(self, request):
        super(ForwardRequest, self).make_request(request)
        self.request, self.header = request, request.header
        self.verb, self.url, self.version = \
            request.verb, request.url, request.version
        self.proc_header()

class ForwardClient(pyweb.HttpClient):
    RequestCls = ForwardRequest

    def __init__(self, hostname, port):
        self.hostname, self.port = hostname, port
    def make_sock(self, sockaddr):
        sock = pyweb.EventletClient()
        sock.connect(self.hostname, self.port)
        return sock

class ProxyForward(ProxyDirect):
    name = 'forward'

    def __init__(self, hostname, port):
        self.hostname, self.port = hostname, port

    def sock_connect(self, sock, request):
        sock.connect(self.hostname, self.port)

    def do_socks(self, request):
        response = request.make_response()
        sock = self.DefaultClient()
        try:
            try: self.sock_connect(sock, request)
            except (EOFError, socket.error): raise pyweb.BadGatewayError()

            sock.sendall(request.make_header() + "".join(request.content))
            res_header = sock.recv_until()
            request.sock.sendall(res_header + '\r\n\r\n')
            response.header_sended = True

            request.timeout.cancel()
            th = spawn(self.trans_loop, request.sock, sock)
            self.trans_loop(sock, request.sock)
            th.wait()
        finally: sock.close()
        response.body_sended, response.connection = True, False
        return response

    def make_client(self): return ForwardClient(self.hostname, self.port)

class SocksClient(pyweb.HttpClient):
    RequestCls = ProxyRequest

    def __init__(self, hostname, port):
        self.hostname, self.port = hostname, port
    def make_sock(self, sockaddr):
        # socks代理的连接数有限，使用pool
        sock = socks.SocksClient()
        sock.auto_connect('%s:%d' % (sockaddr[0], sockaddr[1]),
                          self.hostname, self.port)
        return sock
    def close_sock(self, sock):
        pass

class ProxySocks(ProxyDirect):
    name = 'socks'
    DefaultClient = socks.SocksClient

    def __init__(self, hostname, port):
        self.hostname, self.port = hostname, port

    def sock_connect(self, sock, request):
        sock.auto_connect(request.hostname, self.hostname, self.port)
    def make_client(self): return SocksClient(self.hostname, self.port)
