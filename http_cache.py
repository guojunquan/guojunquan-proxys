#!/usr/bin/python
# -*- coding: utf-8 -*-
# @date: 2010-06-04
# @author: shell.xu
import copy
import lrucache
from http import HttpAction

class HttpCacheFilter (HttpAction):
    MAX_FILE = 16 * 1024

    def __init__ (self, action, size = 256):
        self.next_action = action
        from lrucache import LRUCache
        self.cache = LRUCache (size)

    @staticmethod
    def check_control (r):
        if 'Cache-Control' in r:
            control = r['Cache-Control'].split (',')
            if 'no-cache' in control: return False
            if 'private' in control: return False
        return True

    def check_req (self, request):
        if request.verb != 'GET': return False, False
        if self.check_control (request): return False, True
        return True, True

    safe_codes = [200, 201, 202, 203, 204, 205, 206]
    def check_res (self, response):
        if response.code not in self.safe_codes:
            # print 'code not safe'
            return False
        if not response.cache:
            # print 'cache false'
            return False
        if 'Content-Length' in response and\
                int (response['Content-Length']) > self.MAX_FILE:
            # print 'too much length'
            return False
        if not self.check_control (response): return False
        return True

    def valid_res (self, response):
        # TODO: 验证是否有效
        return True

    def action (self, request):
        check_cache, add_cache = self.check_req (request)
        if check_cache and request.url in self.cache:
            response = self.cache[request.url]
            if self.valid_res (response):
                response = copy.copy (response)
                response.header_sended, response.body_sended = False, False
                response.request, response.socks = request, request.socks
                print 'hit ' + request.url
                return response
            else: del self.cache[request.url]
        response = self.next_action.action (request)
        if add_cache and response is not None and self.check_res (response):
            # print 'cache ' + request.url
            self.cache[request.url] = response
        return response
