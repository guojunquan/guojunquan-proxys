#!/usr/bin/python
# -*- coding: utf-8 -*-
# @date: 2010-06-07
# @author: shell.xu
from __future__ import with_statement
import sys
import base
import zlib
import socket
import eventlet
import datetime
import StringIO
from urlparse import urlparse
import http_proxy
from http import HttpAction
from eventlet.timeout import Timeout as eTimeout

class StringSock(base.SockBase):

    def __init__(self, data): self.recv_rest = data
    def fileno(self): return -1
    def close(self): pass
    def sendall(self, data): raise NotImplementedError()
    def recv(self, size): raise NotImplementedError()

class HttpOverHttpResponse(http_proxy.HttpProxyResponse):

    def append_body(self, data): self.content.append(data)
    def end_body(self): self.body_recved = True

class HttpOverHttpProxy(http_proxy.HttpProxyAction):
    name = 'hoh'
    VERBS = ['OPTIONS', 'GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'TRACE']
    DEBUG = False
    HEADER = 'POST %s HTTP/1.1\r\nConnection: close\r\nContent-Length: %s\r\n\
Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8\r\n\
Accept-Charset: GB2312,utf-8;q=0.7,*;q=0.7\r\nHost: %s\r\n\r\n'

    def __init__(self, shared_pool, proxy_url):
        self.shared_pool, self.proxy_url = shared_pool, proxy_url
        urls = urlparse(proxy_url)
        hostinfo = urls[1].split(':')
        self.host = hostinfo[0]
        self.port = int(hostinfo[1]) if len(hostinfo) > 1 else 80
        self.path = urls[2]
        self.hostname = urls[1]

    def send_appendix(self, request):
        appendix = ['Host: ' + request.hostname,]
        return '\r\n'.join(appendix) + '\r\n\r\n'

    def send_request(self, request):
        if not request.hostname: raise base.NotAcceptableError(request.url)
        rest = request.url.partition(request.hostname)
        request['Connection'] = 'close'
        req_data = [self.send_appendix(request)]
        req_data.append(request.make_headers([request.verb, rest[2],
                                                request.version]))
        req_data.append("".join(request.content))
        req_data = zlib.compress(''.join(req_data), 9)
        req_header = self.HEADER %(self.path, len(req_data), self.host)
        request.socks[1].sendall(req_header + req_data)

    def get_response(self, request):
        if hasattr(request, 'timeout'): request.timeout.cancel()
        res_data = request.make_response(200, HttpOverHttpResponse)
        res_data.socks.reverse()
        try:
            res_data.load_header()
            res_data.recv_body()
        finally: res_data.socks.reverse()
        try: return zlib.decompress(''.join(res_data.content))
        except: raise base.BadGatewayError(''.join(res_data.content))
        
    def send_response(self, request, data):
        idx = data.find('\r\n\r\n')
        appendix, data = data[:idx], data[idx+4:]
        if self.DEBUG: print appendix
        response = request.make_response(200, http_proxy.HttpProxyResponse)
        response.socks = [request.socks[0], StringSock(data)]

        try:
            response.socks.reverse()
            try: response.load_header()
            finally: response.socks.reverse()
            response.send_header()

            response.socks.reverse()
            try: response.recv_body()
            finally: response.socks.reverse()
        except NotImplementedError, err: raise base.BadGatewayError(err)
        return response

    def action(self, request):
        if request.verb not in self.VERBS:
            raise base.MethodNotAllowedError(request.verb)
        request.proxy_count = [0, 0] # send, recv
        request.recv_body()
        try: sock = self.shared_pool.acquire(self.hostname)
        except(EOFError, socket.error): raise base.BadGatewayError()
        if sock is None: raise base.BadGatewayError()
        request.socks.append(sock)
        try:
            self.send_request(request)
            data = self.get_response(request)
            response = self.send_response(request, data)
        finally:
            request.socks.remove(sock)
            self.shared_pool.release(sock, False)
        return response
