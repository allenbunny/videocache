#!/usr/bin/env python
#
# (C) Copyright Kulbir Saini <saini@saini.co.in>
# Product Website : http://cachevideos.com/
#

__author__ = """Kulbir Saini <saini@saini.co.in>"""
__docformat__ = 'plaintext'

from fsop import *
from functools import wraps
from Queue import Queue, Empty

import datetime
import httplib
import logging
import os
import pwd
import re
import shutil
import socket
import sys
import syslog
import time
import traceback
import urllib
import urllib2
import urlparse

try:
    import multiprocessing
    from multiprocessing import synchronize

    if sys.version_info < (2, 7):
        class Popen(multiprocessing.forking.Popen):
            def poll(self, flag = os.WNOHANG):
                if self.returncode is None:
                    while True:
                        try:
                            pid, sts = os.waitpid(self.pid, flag)
                        except OSError, e:
                            if e.errno == errno.EINTR:
                                continue
                            return None
                        else:
                            break
                    if pid == self.pid:
                        if os.WIFSIGNALED(sts):
                            self.returncode = -os.WTERMSIG(sts)
                        else:
                            assert os.WIFEXITED(sts)
                            self.returncode = os.WEXITSTATUS(sts)
                return self.returncode
        multiprocessing.Process._Popen = Popen

    multiprocessing_enabled = True
except:
    print traceback.format_exc()
    multiprocessing_enabled = False

class TimeoutError(Exception):
    pass

def with_timeout(tmout, raise_exception = True):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if multiprocessing_enabled:
                q = multiprocessing.Queue()
                subproc = multiprocessing.Process(target=f, args=(q,) + args, kwargs=kwargs)
                subproc.start()
                subproc.join(tmout)
                subproc.terminate()
                try:
                    return q.get(timeout = 0.1)
                except Empty:
                    if raise_exception: raise TimeoutError
                    return False
            else:
                q = Queue()
                f(q, *args, **kwargs)
                try:
                    return q.get(timeout = 0.1)
                except Empty:
                    if raise_exception: raise TimeoutError
                    return False
        return wrapper
    return decorator

def classmethod_with_timeout(tmout, raise_exception = True):
    def decorator(f):
        @wraps(f)
        def wrapper(klass, *args, **kwargs):
            if multiprocessing_enabled:
                q = multiprocessing.Queue()
                subproc = multiprocessing.Process(target=f, args=(klass, q) + args, kwargs=kwargs)
                subproc.start()
                subproc.join(tmout)
                subproc.terminate()
                try:
                    return q.get(timeout = 0.1)
                except Empty:
                    if raise_exception: raise TimeoutError
                    return False
            else:
                q = Queue()
                f(klass, q, *args, **kwargs)
                try:
                    return q.get(timeout = 0.1)
                except Empty:
                    if raise_exception: raise TimeoutError
                    return False
        return wrapper
    return decorator

def timeout_exec(timeout, f, raise_exception, *args, **kwargs):
    @with_timeout(timeout, raise_exception)
    def _new_ret_method(q, *args, **kwargs):
        q.put(f(*args, **kwargs))
    return _new_ret_method(*args, **kwargs)

# Alias urllib2.open to urllib2.urlopen
urllib2.open = urllib2.urlopen

VALIDATE_DOMAIN_PORT_REGEX = re.compile('^[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,6}(:[0-9]{1,5})?$')
VALIDATE_EMAIL_REGEX = re.compile('^[^@\ ]+@([A-Za-z0-9]+.){1,3}[A-Za-z]{2,6}$')
VALIDATE_IP_ADDRESS_REGEX = re.compile('^(((25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?))$')
VALIDATE_MAC_ADDRESS_REGEX = re.compile('([0-9A-F]{2}:){5}[0-9A-F]{2}', re.I)

LOG_LEVEL_INFO = logging.getLevelName(logging.INFO)
LOG_LEVEL_ERR = logging.getLevelName(logging.ERROR)
LOG_LEVEL_WARN = logging.getLevelName(logging.WARN)

# Colored messages on terminal
def red(msg):
    return "\033[1;31m%s\033[0m" % msg

def blue(msg):
    return "\033[1;36m%s\033[0m" % msg

def green(msg):
    return "\033[1;32m%s\033[0m" % msg

def syslog_msg(msg):
    syslog.syslog(syslog.LOG_ERR | syslog.LOG_DAEMON, msg)

def build_message(params):
    cur_time = time.time()
    local_time = time.strftime(params.get('timeformat', '%d/%b/%Y:%H:%M:%S'), time.localtime())
    gmt_time = time.strftime(params.get('timeformat', '%d/%b/%Y:%H:%M:%S'), time.gmtime())
    return params.get('logformat', '') % { 'timestamp' : int(cur_time), 'timestamp_ms' : round(cur_time, 3), 'localtime' : local_time, 'gmt_time' : gmt_time, 'process_id' : params.get('process_id', '-'), 'levelname' : params.get('levelname', '-'), 'client_ip' : params.get('client_ip', '-'), 'website_id' : params.get('website_id', '-').upper(), 'code' : params.get('code', '-'), 'video_id' : params.get('video_id', '-'), 'size' : params.get('size', '-'), 'message' : params.get('message', '-'), 'debug' : params.get('debug', '-') }

def refine_url(url, arg_drop_list = []):
    """Returns a refined url with all the arguments mentioned in arg_drop_list dropped."""
    if len(arg_drop_list) == 0:
        return url
    query = urlparse.urlsplit(url)[3]
    new_query = '&'.join(['='.join(j) for j in filter(lambda x: x[0] not in arg_drop_list, [i.split('=') for i in query.split('&')])])
    return (urllib.splitquery(url)[0] + '?' + new_query.rstrip('&')).rstrip('?')

def current_time():
    return int(time.time())

def datetime_to_timestamp(t):
    return int(time.mktime(t.timetuple()))

def timestamp_to_datetime(t):
    return datetime.datetime.fromtimestamp(float(t))

def is_valid_domain_port(name):
    if VALIDATE_DOMAIN_PORT_REGEX.match(name):
        return True
    return False

def is_valid_ip(ip):
    try:
        if len(filter(lambda x: 0 <= int(x) <= 255, ip.split('.'))) == 4:
            return True
    except Exception, e:
        pass
    return False

def is_valid_host_port(host_port, port_optional = False):
    if is_valid_domain_port(host_port): return True

    if ':' in host_port:
        ip, port = host_port.split(':')
        if not port.isdigit():
            return False
        port = int(port)
        if port < 0 or port > 65535:
            return False
    elif not port_optional:
        return False
    return is_valid_ip(host_port.split(':')[0])

def is_valid_email(email):
    if VALIDATE_EMAIL_REGEX.match(email):
        return True
    return False

def is_valid_user(user):
    try:
        pwd.getpwnam(user)
        return True
    except:
        return False

def is_integer(number):
    try:
        int(number)
        return True
    except:
        return False

def is_float(number):
    try:
        float(number)
        return True
    except:
        return False

def is_ascii(string):
    try:
        string.decode('ascii')
        return True
    except Exception, e:
        return False

def is_ip_address(string):
    return VALIDATE_IP_ADDRESS_REGEX.match(string)

def is_mac_address(string):
    return VALIDATE_MAC_ADDRESS_REGEX.search(string)

def max_or_empty(sequence):
    if len(sequence) == 0:
        return sequence.__class__()
    else:
        return max(sequence)

def min_or_empty(sequence):
    if len(sequence) == 0:
        return sequence.__class__()
    else:
        return min(sequence)

def chunks(l, n):
    for i in xrange(0, len(l), n):
        yield l[i:i+n]

# Extending urllib2 to support HTTP HEAD requests.
class HeadRequest(urllib2.Request):
    def get_method(self):
        return 'HEAD'

# Extending urllib2 to support HTTP PURGE requests to PURGE objects from Squid cache.
class PurgeRequest(urllib2.Request):
    def get_method(self):
        return 'PURGE'

# Videocache setup/update specific functions
def print_message_and_abort(message):
    print >>sys.stderr, message
    sys.exit(1)

def log_traceback():
    print blue('\n' + '-' * 25 + 'Traceback Begin' + '-' * 25)
    print traceback.format_exc(),
    print blue('-' * 25 + 'Traceback End' + '-' * 27 + '\n')

def generate_httpd_conf(conf_file, base_dir_list, cache_host, hide_cache_dirs = False, quiet = False):
    """Generates /etc/httpd/conf.d/videocache.conf for apache web server for serving videos."""
    cache_host_ip = cache_host.split(':')[0]
    if hide_cache_dirs:
        hide = "-Indexes"
    else:
        hide = "+Indexes"

    videocache_conf = """##############################################################################
#                                                                            #
# file : """ + conf_file + " "*(68 - len(conf_file)) + """#
#                                                                            #
# Videocache is a squid url rewriter to cache videos from various websites.  #
# Check http://cachevideos.com/ for more details.                            #
#                                                                            #
# ----------------------------- Note This ---------------------------------- #
# Don't change this file under any circumstances.                            #
# Use /etc/videocache.conf to configure Videocache.                          #
#                                                                            #
##############################################################################\n\n"""
    for dir in base_dir_list:
        if len(base_dir_list) == 1:
            videocache_conf += "\nAlias /videocache " + dir
        else:
            videocache_conf += "\nAlias /videocache/" + str(base_dir_list.index(dir)) + " " + dir

        videocache_conf += """
<Directory %s>
  Options %s
  Order Allow,Deny
  Allow from all
  <IfModule mod_headers.c>
    Header add Videocache "3.x"
    Header add X-Cache "HIT from %s"
  </IfModule>
  <IfModule mod_mime.c>
    AddType video/webm .webm
    AddType application/vnd.android.package-archive .android
  </IfModule>
</Directory>\n""" % (dir, hide, cache_host_ip)

    try:
        file = open(conf_file, 'w')
        file.write(videocache_conf)
        file.close()
        if not quiet: print "Generated config file : " + conf_file
    except:
        if not quiet: print "Failed to generate config file : " + conf_file
        log_traceback()
        return False
    return True

# Networking Related
def is_port_open(ip, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.connect((ip, int(port)))
        s.shutdown(2)
        return True
    except:
        return False

def test_url(url, proxy = None):
    try:
        opener = urllib2
        if proxy:
            opener = urllib2.build_opener(urllib2.ProxyHandler ({ 'http': o.this_proxy }))
        request = opener.open(url)
        request.close()
        return True
    except Exception, e:
        if 'code' in dir(e):
            return e.code
        else:
            return False

# Functions related to cache_period option
# Cache Period from Hash to String
def cache_period_h2s(cache_period):
    return '%02d:%02d-%02d:%02d' % (cache_period['start'][0], cache_period['start'][1], cache_period['end'][0], cache_period['end'][1])

# Cache Period from String to List of Hashes
def cache_period_s2lh(cache_period):
    try:
        if cache_period.strip() == '':
            return None
        else:
            return map(lambda x: { 'start' : x[0], 'end' : x[1] }, map(lambda x: map(lambda y: [int(z) for z in y.split(':')], x.split('-')), [i.strip().replace(' ', '') for i in cache_period.strip().split(',')]))
    except Exception, e:
        return False

# Bind Source IP
class BindableHTTPConnection(httplib.HTTPConnection):
    def connect(self):
        """Connect to the host and port specified in __init__."""
        self.sock = socket.socket()
        if self.source_ip:
            self.sock.bind((self.source_ip, 0))
        if isinstance(self.timeout, float):
            self.sock.settimeout(self.timeout)
        self.sock.connect((self.host,self.port))

def BindableHTTPConnectionFactory(source_ip = None):
    def _get(host, port=None, strict=None, timeout=0):
        bhc=BindableHTTPConnection(host, port=port, strict=strict, timeout=timeout)
        bhc.source_ip=source_ip
        return bhc
    return _get
