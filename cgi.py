#!/usr/bin/python
import os
import sys
import zlib
import time
import socket
import select
import datetime
import threading

class SockBase (object):
    buffer_size = 2096

    def __init__ (self, host, port, fdo):
        self.recv_rest, self.fdo = "", fdo
        self.sock = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect ((host, port))
        self.poll = select.poll ()
        self.poll.register (self.sock.fileno (), select.POLLIN | select.POLLHUP)
        self.poll.register (fdo, select.POLLHUP)

    def close (self):
        self.poll.unregister (self.fdo)
        self.poll.unregister (self.sock.fileno ())
        self.sock.close ()

    def recv (self, size):
        for fd, event in self.poll.poll ():
            if event & select.POLLIN:
                data = os.read (fd, size)
                if len (data) == 0: raise EOFError ()
                yield data
            if event & select.POLLHUP: raise EOFError ()

    def recv_once (self, size = 0):
        if size == 0: size = self.buffer_size
        if not self.recv_rest: return ''.join (self.recv (size))
        self.recv_rest, data = "", self.recv_rest
        return data

    def recv_until (self, break_str = "\r\n\r\n"):
        while self.recv_rest.find (break_str) == -1:
            self.recv_rest += ''.join (self.recv (self.buffer_size))
        idx = self.recv_rest.find (break_str)
        data = self.recv_rest[:idx]
        self.recv_rest = self.recv_rest[idx + len (break_str):]
        return data

    def recv_length (self, length):
        while len (self.recv_rest) < length:
            self.recv_rest += ''.join (self.recv (self.buffer_size))
        data, self.recv_rest = self.recv_rest[:length], self.recv_rest[length:]
        return data

class Timeout (threading.Thread):
    def __init__ (self, timeout, func):
        threading.Thread.__init__ (self)
        self.timeout, self.func = timeout, func
        self.reset ()
    def reset (self): self.dt = datetime.datetime.now ()
    def run (self):
        while (datetime.datetime.now () - self.dt).seconds < self.timeout:
            time.sleep (2)
        self.func ()

class HoHServer (object):

    def __init__ (self):
        self.timeout = Timeout (30, self.close)
        self.timeout.start ()

    def read_header (self, data):
        header = {}
        for info in data.split ('\r\n'):
            idx = info.find (':')
            if idx == -1: raise Exception ()
            header[info[:idx]] = info[idx+1:].strip ()
        return header

    def read_all (self, fileobj):
        content = []
        while True:
            data = fileobj.read (SockBase.buffer_size)
            if len (data) == 0: break
            content.append (data)
        return zlib.decompress (''.join (content))

    def recv_req (self):
        self.req_info = self.read_all (sys.stdin).split ('\r\n\r\n')
        if len (self.req_info) < 2: raise Exception ()
        req_appendix = self.read_header (self.req_info[0])
        hostinfo = req_appendix['Host'].split (':')
        self.host = hostinfo[0]
        if len (hostinfo) == 1: self.port = 80
        else: self.port = int (hostinfo[1])

    def send_req (self):
        self.sock = SockBase (self.host, self.port, sys.stdout.fileno ())
        self.sock.sock.sendall (self.req_info[1] + '\r\n\r\n')
        if len (self.req_info) > 2: self.sock.sock.sendall (self.req_info[2])

    def check_hasbody (self): return True
    # if self.request.verb == 'HEAD': return False
    # if self.code in [100, 101, 204, 304]: return False
    # return True

    def recv_body (self):
        if self.headers.get ('Transfer-Encoding', 'identity') != 'identity':
            chunk_size = 1
            while chunk_size != 0:
                chunk_data = self.sock.recv_until ('\r\n')
                self.content.append (chunk_data + '\r\n')
                chunk_size = int (chunk_data.split (';')[0], 16)
                main_data = self.sock.recv_length (chunk_size + 2)
                self.content.append (main_data)
        elif 'Content-Length' in self.headers:
            length = int (self.headers['Content-Length'])
            self.content.append (self.sock.recv_length (length))
        elif self.check_hasbody ():
            try:
                while True: self.content.append (self.sock.recv_once ())
            except (EOFError, socket.error): pass

    def recv_res (self):
        self.headers, self.content = {}, []
        self.header = self.sock.recv_until ()
        header_lines = self.header.split ('\r\n')
        for line in header_lines[1:]:
            part = line.split (":")
            if len (part) == 1: raise Exception ()
            self.headers[part[0]] = part[1].strip ()
        self.recv_body ()
        appendix = 'appendix'
        data = '\r\n\r\n'.join ([appendix, self.header, ''.join (self.content)])
        sys.stdout.write (zlib.compress (data, 9))

    def close (self):
        if hasattr (self, 'sock'): self.sock.close ()
        sys.stdout.flush ()
        sys.exit (0)

if __name__ == "__main__":
    print 'Content-Type: text/html; charset=ISO-8859-4\r\nConnection: close\r\n'
    srv = HoHServer ()
    try:
        try:
            srv.recv_req ()
            srv.send_req ()
            srv.recv_res ()
        except Exception, err:
            import traceback
            print traceback.format_exc ()
    finally: srv.close ()
