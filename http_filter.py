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
from eventlet.timeout import Timeout as eTimeout

class HttpGfwProxyDispatcher (HttpAction):
    VERBS = ['OPTIONS', 'GET', 'HEAD', 'POST', 'PUT', 'DELETE', 'TRACE']
    url_map = {}

    def __init__ (self, default_action = None):
        self.gfwlist, self.default, self.working = [], default_action, {}
        self.sockproxies, self.httpproxies  = [], []

    def add_http (self, proxy): self.httpproxies.append (proxy)
    def add_sock (self, proxy): self.sockproxies.append (proxy)
        
    def loadgfw (self, gfwpath = 'gfw'):
        if gfwpath is None: gfwpath = self.gfwpath
        else: self.gfwpath = gfwpath
        with open (gfwpath, 'r') as gfwfile:
            for line in gfwfile: self.gfw_append (line.strip ().lower ())
        self.gfwlist.sort ()

    def savegfw (self, gfwpath = None):
        if gfwpath is None: gfwpath = self.gfwpath
        with open (gfwpath, 'w+') as gfwfile:
            gfwfile.write ('\n'.join (self.gfwlist))
    
    def gfw_append (self, h):
        if h not in self.gfwlist: self.gfwlist.append (h)

    def gfw_check (self, h):
        for g in self.gfwlist:
            if h.endswith (g): return True

    def gfw_action (self, request):
        if request.verb in self.VERBS and len (self.httpproxies) > 0:
            for s in self.httpproxies:
                request.action = s
                try: return s.action (request)
                except (EOFError, socket.error): pass
        for s in self.sockproxies:
            request.action = s
            try: return s.action (request)
            except (EOFError, socket.error): pass
        raise base.HttpException (501)

    def direct_failed (self, request):
        return self.gfw_action (request)

    def action (self, request):
        if not request.hostname:
            for url, action in self.url_map.items ():
                if request.urls['path'].startswith (url):
                    return action (self, request)
      	    raise base.NotFoundError (request.urls['path'])
        request.action = None
        self.working[request] = datetime.datetime.now ()
        try:
            hostinfo = request.hostname.partition (':')
            if self.gfw_check (hostinfo[0].lower ()):
                return self.gfw_action (request)
            else:
                try:
                    request.action = self.default
                    return self.default.action (request)
                except (EOFError, socket.error): return self.direct_failed (request)
                # except base.TimeoutException: return self.direct_failed (request)
        finally: del self.working[request]

    html_header = '<html>\n<head><title>%s</title></head>\n<body>\n'
    def action_status (self, request):
        response = request.make_response ()
        response.append_body (self.html_header % 'url list')
        table_header = 'length: %d<br><table width="100%%"><thead>\
<td>verb</td><td>url</td><td>action name</td><td>Elapse</td><td>from addr</td>\
<td>send count</td><td>recv count</td></thead><tbody>\n' % len (self.working)
        response.append_body (table_header)
        dtnow = datetime.datetime.now ()
        for req, dt in self.working.items ():
            dd = dtnow - dt
            line = '<tr><td>%s</td><td><a href="/cutoff?from=%s:%d">%s</a></td>\
<td>%s</td><td>%d.%d</td><td>%s:%d</td><td>%d</td><td>%d</td></tr>\n' %\
                (req.verb, req.from_addr[0], req.from_addr[1], req.url,
                 req.action.name if hasattr (req.action, 'name') else "",
                 dd.seconds, dd.microseconds, req.from_addr[0], req.from_addr[1],
                 req.proxy_count[0] if hasattr (req, 'proxy_count') else 0,
                 req.proxy_count[1] if hasattr (req, 'proxy_count') else 0,)
            response.append_body (line)
        response.append_body ('</tbody></table><pre>\n')
        response.append_body (eventlet.debug.format_hub_listeners ())
        response.append_body ('</pre></body>\n</html>')
        return response
    url_map['/status'] = action_status

    def action_cutoff (self, request):
        from_addr = request.get_params_dict (
            request.urls.get ('query', ''))['from'].split (':')
        from_addr[1] = int (from_addr[1])
        from_addr = tuple (from_addr)
        for req in self.working.keys ():
            if req.from_addr == from_addr:
                req.term ()
                del self.working[req]
                return request.make_redirect ('/status')
        response = request.make_response (500)
        response['Content-Type'] = 'text/plain; charset=ISO-8859-1'
        response.append_body ('request not found')
        return response
    url_map['/cutoff'] = action_cutoff

    def action_gfwlist (self, request):
        response = request.make_response ()
        response.append_body (self.html_header % 'gfw list')
        response.append_body ('<form action="/gfwadd" method="post">\
<input type="text" name="host"/><input type="submit" value="Submit"/>\
</form><a href="/gfwsave">save</a><br/>')
        response.append_body ('<table><thead><td>hostname</td>\
<td>action</td></thead><tbody>')
        for hostname in self.gfwlist:
            response.append_body ('<tr><td>%s</td><td><a href="/gfwdel?host=%s">\
del</a></td></tr>' % (hostname, hostname))
        response.append_body ('</tbody></table></body>\n</html>')
        return response
    url_map['/gfwlist'] = action_gfwlist
    
    def action_gfwdel (self, request):
        host = request.get_params_dict (request.urls.get ('query', ''))['host']
        if host in self.gfwlist: self.gfwlist.remove (host)
        return request.make_redirect ('/gfwlist')
    url_map['/gfwdel'] = action_gfwdel

    def action_gfwadd (self, request):
        request.recv_body ()
        host = request.get_params_dict (''.join (request.content))['host']
        self.gfw_append (host)
        self.gfwlist.sort ()
        return request.make_redirect ('/gfwlist')
    url_map['/gfwadd'] = action_gfwadd

    def action_gfwsave (self, request):
        self.savegfw ()
        return request.make_redirect ('/gfwlist')
    url_map['/gfwsave'] = action_gfwsave

    def action_gfwload (self, request):
        self.loadgfw (None)
        return request.make_redirect ('/gfwlist')
    url_map['/gfwload'] = action_gfwload
