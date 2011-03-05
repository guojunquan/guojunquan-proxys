#!/usr/bin/python
# -*- coding: utf-8 -*-
'''
@date: 2010-06-07
@author: shell.xu
'''
import SocketServer

class ProxyHandler(SocketServer.StreamRequestHandler):

	def proxy_header(self, name, value):
		pass

	def read_header(self, src):
		line = src.readline().strip()
		info, header = line.split(), {}
		while True:
			line = src.readline().strip()
			if not len(line): break
			a, sp, b = line.partition(':')
			if not sp: raise Exception('wrong header')
			if a.strip().lower().startswith('proxy'):
				self.proxy_header(a.strip(), b.strip())
			else: headers[a.strip()] = b.strip()
		return info, headers

	def read_body_chunked(self):
		raise NotImplmentedError

	def make_data(self, info, headers, body):
		return ''

	def handle(self):
		info, headers = self.read_header(self.rfile)
		if 'Content-Length' in headers:
			length = int(headers['Content-Length'])
			body = self.rfile.read(length)
		elif headers.get('Transfer-Encoding', 'identity') != 'identity':
			body = self.read_body_chunked()
		else: body = ''
		data = self.make_data(info, headers, body)
		
		

if __name__ == '__main__':
	srv = SocketServer.TCPServer(('', 8001), ProxyHandler)
	srv.serve_forever()
