#!/usr/bin/python
# -*- coding: utf-8 -*-
# @date: 2010-10-27
# @author: shell.xu
from __future__ import with_statement
import os
import sys
import datetime
import pyweb

class DomainFilter(object):

    def __init__(self, filepath): self.filepath, self.domains = filepath, {}

    def add(self, domain):
        doptr, chunk, domain = self.domains, domain.split('.'), domain.lower()
        for c in reversed(chunk):
            if len(c.strip()) == 0: continue
            if c not in doptr or doptr[c] is None: doptr[c] = {}
            lastptr, doptr = doptr, doptr[c]
        if len(doptr) == 0: lastptr[c] = None

    def remove(self, domain):
        doptr, stack, chunk = self.domains, [], domain.split('.')
        for c in reversed(chunk):
            if len(c.strip()) == 0: raise LookupError()
            if doptr is None: return False
            stack.append(doptr)
            if c not in doptr: return False
            doptr = doptr[c]
        for doptr, c in zip(reversed(stack), chunk):
            if doptr[c] is None or len(doptr[c]) == 0: del doptr[c]
        return True

    def __getitem__(self, domain):
        doptr, chunk = self.domains, domain.split('.')
        for c in reversed(chunk):
            if len(c.strip()) == 0: continue
            if c not in doptr: return False
            doptr = doptr[c]
            if doptr is None: break
        return doptr
    def __contains__(self, domain): return self.__getitem__(domain) is None

    def getlist(self, d = None, s = ''):
        if d is None: d = self.domains
        for k, v in d.items():
            t = '%s.%s' %(k, s)
            if v is None: yield t.strip('.')
            else:
                for i in self.getlist(v, t): yield i

    def show(self, d = None, s = 0):
        if d is None: d = self.domains
        for k, v in d.items():
            yield '  '*s + k
            if v is not None:
                for i in self.show(v, s + 1): yield i

    def load(self):
        with open(self.filepath, 'r') as gfwfile:
            for line in gfwfile: self.add(line.strip().lower())

    def save(self):
        selflist = []
        for i in self.getlist(): selflist.append(i)
        selflist.sort()
        with open(self.filepath, 'w+') as gfwfile:
            gfwfile.write('\n'.join(selflist))

class DispatchGFW(object):
    VERBS = ['CONNECT',]
    url_map = {}

    def __init__(self, non_gfw = None, gfwpath = 'gfw'):
        self.non_gfw, self.working = non_gfw, {}
        self.gfw = DomainFilter(gfwpath)
        self.gfw.load()
        self.gfw_http, self.gfw_sock = [], []

    def add_http(self, proxy): self.gfw_http.append(proxy)
    def add_sock(self, proxy): self.gfw_sock.append(proxy)

    def do_list(self, request, l):
        for p in l:
            request.app = p
            try: return p(request)
            except(EOFError, socket.error, base.HttpException): pass

    def __call__(self, request):
        if not request.hostname:
            for url, action in self.url_map.items():
                if request.urls.path.startswith(url):
                    return action(self, request)
      	    raise base.NotFoundError(request.urls.path)
        request.app = None
        self.working[request] = datetime.datetime.now()
        try:
            hostinfo = request.hostname.partition(':')
            if hostinfo[0].strip().lower() not in self.gfw:
                request.app = self.non_gfw
                return request.app(request)
            if request.verb not in self.VERBS and len(self.gfw_http) > 0:
                response = self.do_list(request, self.gfw_http)
                if response: return response
            response = self.do_list(request, self.gfw_sock)
            if response: return response
            raise base.HttpException(501)
        finally: del self.working[request]

    tpl_status = pyweb.Template(template = '''<html><head><title>url list</title></head><body>length: {%=len(working)%}<br><table width="100%%"><thead><td>verb</td><td>url</td><td>action name</td><td>Elapse</td><td>from addr</td><td>send count</td><td>recv count</td></thead><tbody>{%for req, dt in working.items():%}{%dd = dtnow - dt%}{%sockaddr = '%s:%d' % (req.sock.from_addr[0], req.sock.from_addr[1])%}<tr><td>{%=req.verb%}</td><td><a href="/cutoff?from={%=sockaddr%}">req.urls.path</a></td><td>{%=req.app%}</td><td>{%=dd.seconds%}.{%=dd.microseconds%}</td><td>{%=sockaddr%}</td><td>req.proxy_count[0]</td><td>req.proxy_count[1]</td></tr>{%end%}</tbody></table></body></html>''')
    def action_status(self, request):
        response = request.make_response()
        info = {'working': self.working, 'dtnow': datetime.datetime.now()}
        self.tpl_status.render_res(response, info)
        response.connection = False
        return response
    url_map['/status'] = action_status

    tpl_gfwlist = pyweb.Template(template = '<html><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8"/><title>gfw list</title></head><body><form action="/gfwadd" method="post"><input type="text" name="host"/><input type="submit" value="Submit"/></form><a href="/gfwload">load</a>|<a href="/gfwsave">save</a><br/><table><thead><td>hostname</td><td>action</td></thead><tbody>{%for hostname in gfwlist:%}<tr><td>{%=hostname%}</td><td><a href="/gfwdel?host={%=hostname%}">del</a></td></tr>{%end%}</tbody></table></body>\n</html>')
    def action_gfwlist(self, request):
        response = request.make_response()
        info = {'gfwlist': self.gfw.getlist(),}
        self.tpl_gfwlist.render_res(response, info)
        response.connection = False
        return response
    url_map['/gfwlist'] = action_gfwlist
    
    def action_gfwdel(self, request):
        host = request.get_params()['host']
        print host
        if self.gfw.remove(host.strip().lower()):
            return request.make_redirect('/gfwlist')
        response = request.make_response(500)
        response['Content-Type'] = 'text/plain; charset=ISO-8859-1'
        response.append_body('remove failed')
        return response
    url_map['/gfwdel'] = action_gfwdel

    def action_gfwadd(self, request):
        request.recv_body()
        host = request.post_params()['host']
        self.gfw.add(host.strip())
        return request.make_redirect('/gfwlist')
    url_map['/gfwadd'] = action_gfwadd

    def action_gfwsave(self, request):
        self.gfw.save()
        return request.make_redirect('/gfwlist')
    url_map['/gfwsave'] = action_gfwsave

    def action_gfwload(self, request):
        self.gfw.load()
        return request.make_redirect('/gfwlist')
    url_map['/gfwload'] = action_gfwload
