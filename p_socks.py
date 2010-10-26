#!/usr/bin/python
# -*- coding: utf-8 -*-
# @date: 2010-10-27
# @author: shell.xu
from __future__ import with_statement
import os
import sys
import pyweb

class ProxyRequest(pyweb.HttpRequest):

    def make_request(self, request):
        super(ProxyRequest, self).make_request(request.url)
        self.request = request
        self.header = request.header
        self.verb, self.version = request.verb, request.version

    def make_response(self, code = 200):
        response = ProxyResponse(self, code)
        # if self.get_header('connection', '').lower() == 'close' or \
        #         code >= 500 or self.version.upper() != 'HTTP/1.1':
        response.connection = False
        return response

class ProxyResponse(pyweb.HttpResponse):

    def send_header(self, auto = False):
        if self.header_sended: return
        self.request.responsed = True
        if auto and 'content-length' not in self.header:
            self.set_header('content-length', self.body_len())
        self.request.request.sock.sendall(self.make_header())
        self.header_sended = True

    def append_body(self, data):
        self.send_body(data)

    def send_body(self, data):
        ''' 发送一个数据片段 '''
        if not self.chunk_mode: self.request.request.sock.sendall(data)
        else: self.request.request.sock.sendall('%x\r\n%s\r\n' %(len(data), data))

class ProxyClient(pyweb.HttpClient):
    RequestCls = ProxyRequest

class ProxyBase(object):
    VERB_SOCKS = ['CONNECT', ]

    def __call__(self, request):
        if request.verb in self.VERB_SOCKS:
            return self.do_socks(request)
        else: return self.do_http(request)

class ProxyDirect(ProxyBase):
    def __init__(self):
        pass

    def do_socks(self, request):
        pass

    def do_http(self, request):
        request.recv_body()
        client = ProxyClient()
        preq = client.make_request(request)
        response = client.handler(preq)
        response.send_header()
        response.recv_body()
        response.body_sended = True
        return response

class ProxyForward(ProxyBase):
    def __init__(self):
        pass
    def do_socks(self, request):
        pass
    def do_http(self, request):
        pass
    
class ProxySocks(ProxyBase):
    def __init__(self):
        pass
    def do_socks(self, request):
        pass
    def do_http(self, request):
        pass
