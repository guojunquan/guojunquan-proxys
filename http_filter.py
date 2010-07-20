#!/usr/bin/python
# -*- coding: utf-8 -*-
# @date: 2010-06-04
# @author: shell.xu
from __future__ import with_statement
import base
import socket
import eventlet
import datetime
from http import HttpAction

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

class HttpGfwProxyDispatcher(HttpAction):
    VERBS = ['CONNECT',]
    url_map = {}

    def __init__(self, default_action = None, gfwpath = 'gfw'):
        self.default, self.working = default_action, {}
        self.gfw = DomainFilter(gfwpath)
        self.gfw.load()
        self.sockproxies, self.httpproxies  = [], []

    def add_http(self, proxy): self.httpproxies.append(proxy)
    def add_sock(self, proxy): self.sockproxies.append(proxy)
        
    def action(self, request):
        if not request.hostname:
            for url, action in self.url_map.items():
                if request.urls['path'].startswith(url):
                    return action(self, request)
      	    raise base.NotFoundError(request.urls['path'])
        request.action = None
        self.working[request] = datetime.datetime.now()
        try:
            hostinfo = request.hostname.partition(':')
            if hostinfo[0].strip().lower() not in self.gfw:
                request.action = self.default
                return self.default.action(request)
            if request.verb not in self.VERBS and len(self.httpproxies) > 0:
                for s in self.httpproxies:
                    request.action = s
                    try: return s.action(request)
                    except(EOFError, socket.error, base.HttpException): pass
            for s in self.sockproxies:
                request.action = s
                try: return s.action(request)
                except(EOFError, socket.error, base.HttpException): pass
            raise base.HttpException(501)
        finally: del self.working[request]

    html_header = '<html>\n<head><title>%s</title></head>\n<body>\n'
    def action_status(self, request):
        response = request.make_response()
        response.append_body(self.html_header % 'url list')
        table_header = 'length: %d<br><table width="100%%"><thead>\
<td>verb</td><td>url</td><td>action name</td><td>Elapse</td><td>from addr</td>\
<td>send count</td><td>recv count</td></thead><tbody>\n' % len(self.working)
        response.append_body(table_header)
        dtnow = datetime.datetime.now()
        for req, dt in self.working.items():
            dd = dtnow - dt
            line = '<tr><td>%s</td><td><a href="/cutoff?from=%s:%d">%s</a></td>\
<td>%s</td><td>%d.%d</td><td>%s:%d</td><td>%d</td><td>%d</td></tr>\n' %\
                (req.verb, req.from_addr[0], req.from_addr[1], req.url,
                 req.action.name if hasattr(req.action, 'name') else "",
                 dd.seconds, dd.microseconds, req.from_addr[0], req.from_addr[1],
                 req.proxy_count[0] if hasattr(req, 'proxy_count') else 0,
                 req.proxy_count[1] if hasattr(req, 'proxy_count') else 0,)
            response.append_body(line)
        response.append_body('</tbody></table><pre>\n')
        response.append_body(eventlet.debug.format_hub_listeners())
        response.append_body('</pre></body>\n</html>')
        return response
    url_map['/status'] = action_status

    def action_gfwlist(self, request):
        response = request.make_response()
        response.append_body(self.html_header % 'gfw list')
        response.append_body('<form action="/gfwadd" method="post">\
<input type="text" name="host"/><input type="submit" value="Submit"/>\
</form><a href="/gfwload">load</a>|<a href="/gfwsave">save</a><br/>')
        response.append_body('<table><thead><td>hostname</td>\
<td>action</td></thead><tbody>')
        for hostname in self.gfw.getlist():
            response.append_body('<tr><td>%s</td><td><a href="/gfwdel?host=%s">\
del</a></td></tr>' %(hostname, hostname))
        response.append_body('</tbody></table></body>\n</html>')
        return response
    url_map['/gfwlist'] = action_gfwlist
    
    def action_gfwdel(self, request):
        host = request.get_params_dict(request.urls.get('query', ''))['host']
        if self.gfw.remove(host.strip().lower()):
            return request.make_redirect('/gfwlist')
        response = request.make_response(500)
        response['Content-Type'] = 'text/plain; charset=ISO-8859-1'
        response.append_body('remove failed')
        return response
    url_map['/gfwdel'] = action_gfwdel

    def action_gfwadd(self, request):
        request.recv_body()
        host = request.get_params_dict(''.join(request.content))['host']
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
