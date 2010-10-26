#!/usr/bin/python
# -*- coding: utf-8 -*-
# @date: 2010-06-04
# @author: shell.xu
import socket
import struct
from pyweb import EventletClient

PROXY_TYPE_SOCKS4 = 1
PROXY_TYPE_SOCKS5 = 2

def fmt_string(data): return chr(len(data)) + data

class GeneralProxyError(socket.error):
    __ERRORS =("success", "invalid data", "not connected", "not available",
                "bad proxy type", "bad input")
    def __init__(self, id, *params):
        if id in self.__ERRORS: params.insert(0, self.__ERRORS[id])
        super(GeneralProxyError, self).__init__(*params)
class Socks4Error(GeneralProxyError):
    __ERRORS =("request granted", "request rejected or failed",
                "request rejected because SOCKS server cannot connect to identd \
on the client", "request rejected because the client program and identd report \
different user-ids", "unknown error")
    def __init__(self, *params):
        super(Socks4Error, self).__init__(*params)
class Socks5Error(GeneralProxyError):
    __ERRORS =("succeeded", "general SOCKS server failure",
                "connection not allowed by ruleset", "Network unreachable",
                "Host unreachable", "Connection refused", "TTL expired",
                "Command not supported", "Address type not supported",
                "Unknown error")
    def __init__(self, *params):
        super(Socks5Error, self).__init__(*params)
class Socks5AuthError(GeneralProxyError):
    __ERRORS =("succeeded", "authentication is required",
                "all offered authentication methods were rejected",
                "unknown username or invalid password", "unknown error")
    def __init__(self, *params):
        super(Socks5AuthError, self).__init__(*params)

class TcpSocksClient(EventletClient):

    def socks5_auth(self, username, password):
        if username is None or password is None: self.sendall("\x05\x01\x00")
        else: self.sendall("\x05\x02\x00\x02")
        chosenauth = self.recv_length(2)
        if chosenauth[0] != "\x05": raise GeneralProxyError(1)
        if chosenauth[1] == "\x00": pass
        elif chosenauth[1] == "\x02":
            self.sendall('\x01' + fmt_string(username) + fmt_string(password))
            authstat = self.recv_length(2)
            if authstat[0] != "\x01": raise GeneralProxyError(1)
            if authstat[1] != "\x00": raise Socks5AuthError(3)
        else:
            if chosenauth[1] == "\xFF": raise Socks5AuthError(2)
            else: raise GeneralProxyError(1)
            
    def socks5_connect(self, addr, port, rdns):
        try:
            self.__proxypeername =(addr, port)
            reqaddr = "\x01" + socket.inet_aton(addr)
        except socket.error:
            if rdns: reqaddr = '\x03' + fmt_string(addr)
            else:
                ipaddr = socket.gethostbyname(addr)
                reqaddr = "\x01" + socket.inet_aton(ipaddr)
                self.__proxypeername =(ipaddr, port)
        self.sendall("\x05\x01\x00" + reqaddr + struct.pack(">H", port))
        resp = self.recv_length(4)
        if resp[0] != "\x05": raise GeneralProxyError(1)
        if resp[1] != "\x00":
            if ord(resp[1]) <= 8: raise Socks5Error(ord(resp[1]))
            else: raise Socks5Error(9)
        if resp[3] == "\x03": boundaddr = self.recv_length(self.recv_length(1))
        elif resp[3] == "\x01": boundaddr = self.recv_length(4)
        else: raise GeneralProxyError(1)
        boundport = struct.unpack(">H", self.recv_length(2))[0]
        self.__proxysockname =(boundaddr, boundport)

    def socks4_connect(self, addr, port, username, rdns):
        rmtrslv, req = False, ["\x04\x01", struct.pack(">H", port)]
        try:
            self.__proxypeername =(addr, port)
            req.append(socket.inet_aton(addr))
        except socket.error:
            if rdns:
                req.append("\x00\x00\x00\x01")
                rmtrslv = True
            else:
                ipaddr = socket.gethostbyname(addr)
                req.append(socket.inet_aton(ipaddr))
                self.__proxypeername =(ipaddr, port)
        if username is not None: req.append(username)
        req.append("\x00")
        if rmtrslv: req.append(addr + "\x00")
        self.sendall(''.join(req))
        resp = self.recv_length(8)
        if resp[0] != "\x00": raise GeneralProxyError(1)
        if resp[1] != "\x5A":
            if ord(resp[1]) not in(91, 92, 93): raise Socks4Error(4)
            else: raise Socks4Error(ord(resp[1]) - 90)
        self.__proxysockname =(socket.inet_ntoa(resp[4:]),
                                struct.unpack(">H", resp[2:4])[0])

    def connect(self, hostname, addr, port = 1080, username = None,
                 password = None, rdns = True, proxytype = PROXY_TYPE_SOCKS5):
        super(TcpSocksClient, self).connect('%s:%d' %(addr, port,))
        hostinfo = hostname.split(':')
        if len(hostinfo) == 1: target_port = 80
        else: target_port = int(hostinfo[1])
        try:
            if proxytype == PROXY_TYPE_SOCKS5:
                self.socks5_auth(username, password)
                self.socks5_connect(hostinfo[0], target_port, rdns)
            elif proxytype == PROXY_TYPE_SOCKS4:
                self.socks4_connect(hostinfo[0], target_port, username, rdns)
        except GeneralProxyError:
            self.sock.close()
            raise
