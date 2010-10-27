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

    def body_len(self): return self.trans_len[1]
    def append_body(self, data):
        if self.trans_len[1] == 0: self.send_header()
        self.trans_len[1] += len(data)
        self.send_body(data)

    def send_body(self, data):
        ''' 发送一个数据片段 '''
        if not self.chunk_mode: self.src_sock.sendall(data)
        else: self.src_sock.sendall('%x\r\n%s\r\n' %(len(data), data))

class ProxyClient(pyweb.HttpClient):
    RequestCls = ProxyRequest

class ProxyBase(object):
    VERB_SOCKS = ['CONNECT', ]

    def __call__(self, request):
        if request.verb in self.VERB_SOCKS:
            return self.do_socks(request)
        else: return self.do_http(request)

class ProxyDirect(ProxyBase):
    name = 'direct'

    def do_socks(self, request):
        response = request.make_response()
        response.send_header()
        hostname, sp, port = request.hostname.partition(':')
        if port: port = int(port)
        else: port = 80
        sock = pyweb.EventletClient()
        try:
            try: sock.connect(hostname, port)
            except (EOFError, socket.error): raise pyweb.BadGatewayError()
            request.timeout.cancel()
            request.sock.server.pool.spawn_n(self.trans_loop, request.sock, sock)
            self.trans_loop(sock, request.sock)
        finally: sock.close()
        return response
    def trans_loop(self, s1, s2):
        while True: s2.sendall(s1.recv_once())
        s1.close()
        s2.close()

    def make_client(self): return ProxyClient()
    def do_http(self, request):
        request.recv_body()
        client = self.make_client()
        preq = client.make_request(request)
        response = client.handler(preq)
        response.body_sended = True
        return response
