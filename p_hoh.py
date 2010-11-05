#!/usr/bin/python
# -*- coding: utf-8 -*-
# @date: 2010-10-27
# @author: shell.xu
from __future__ import with_statement
import os
import sys

from __future__ import with_statement
import os
import sys
import zlib
import socket
import cPickle
import logging
import urlparse
import traceback
from contextlib import contextmanager
import eventlet
import pyweb
import socks
import p_http

spawn = eventlet.greenthread.spawn

class OverHttpRequest(pyweb.HttpRequest):

    @classmethod
    def make_request(cls, url, self = None):
        if self is None: self = cls(None)
        self = pyweb.HttpRequest.make_request(url, self)
        self.requests = []
        return self

    def proc_client_header(self, header):
        return dict([(k, v) for k, v in header.items()
                     if not k.startswith('proxy-')])

    def add_request(self, request):
        old_header = request.header
        request.header = self.proc_client_header(old_header)
        req = (request.sockaddr, request.make_header() + request.get_body())
        self.requests.append(req)
        request.header = old_header
    def end_request(self):
        self.append_body(zlib.compress(cPickle.dumps(self.requests, 2), 9))

    def make_response(self, code = 200): return OverHttpResponse(self, code)

def OverHttpResponse(pyweb.HttpResponse):

    def iter(self):
        responses = cPickle.loads(zlib.decompress(self.get_body()))
        for header, content in responses:
            response = self.request.make_response()
            lines = header.splitlines()
            for line in lines[1:]:
                if not line.startswith(' ') and not line.startswith('\t'):
                    part = line.partition(":")
                    if not part[1]: raise BadRequestError(line)
                    response.add_header(part[0], part[2].strip())
                else: response.add_header(part[0], line[1:])
            info = lines[0].split()
            response.version, response.code, response.phrase = \
                info[0].upper(), int(info[1]), info[2]
            trans_code = self.get_header('transfer-encoding', 'identity')
            response.chunk_mode = trans_code != 'identity'
            response.append_body(content)
            yield response

class ProxyHttpOverHttp(p_http.ProxyBase):
    name = 'HttpOverHttp'

    def __init__(self, cgi_url, max_size = 10):
        self.cgi_url = cgi_url
        self.pool = eventlet.pools.TokenPool(max_size = max_size)

    @contextmanager
    def item(self):
        with self.pool.item():
            sock = pyweb.EventletClient()
            try: yield sock
            finally: sock.close()
    def connect(self, sock, sockaddr): sock.connect(sockaddr[0], sockaddr[1])

    def do_http(self, request):
        request.recv_body()
        preq = ProxyRequest.make_request(self.cgi_url)
        preq.add_request(request)
        preq.end_request()
        response = pyweb.http_client(preq, sock_factory = self)
        response.body_sended = True
        return response
