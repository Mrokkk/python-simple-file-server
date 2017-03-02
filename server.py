#!/bin/env python3

from aiohttp import web
import os
import sys
import argparse
import mimetypes
import time
import subprocess
import ssl
import string
import logging

html_head = """<!DOCTYPE html>
<html>
<title>Directory listing /$title</title>
<style>
th {{ text-align: left; }}
</style>
<h1>Directory listing /$title</h1>
<hr>
<table>
    <tr>
        <th align="left">Name</th>
        <th style="padding-left: 20pt;">Type</th>
        <th style="padding-left: 20pt;">Modification date</th>
        <th style="padding-left: 20pt;">Size</th>
    </tr>"""

html_foot = """</table>
<hr>
</html>"""

filename_entry = """
    <tr>
        <td><a href="$link">$filename</a></td>
        <td style="padding-left: 20pt;">$filetype</td>
        <td style="padding-left: 20pt;">$mtime</td>
        <td style="padding-left: 20pt;">$size</td>
    </tr>
"""


def human_readable_size(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def directory_listing_body(dirname):
    body = string.Template(html_head).substitute(title=dirname)
    real_dirname = os.path.join(os.getcwd(), dirname)
    for filename in os.listdir(real_dirname):
        realpath = os.path.join(real_dirname, filename)
        file_type = 'Dir' if os.path.isdir(realpath) else 'File'
        link_path = '/' + os.path.relpath(realpath, os.getcwd())
        body += string.Template(filename_entry).substitute(link=link_path,
                    filename=filename,
                    filetype=file_type,
                    mtime=time.ctime(os.path.getmtime(realpath)),
                    size=human_readable_size(os.path.getsize(realpath)))
    body += html_foot
    return body


async def binary_file_response(filename, filetype, request):
    resp = web.StreamResponse(headers={
        'Content-Type': filetype,
        'Content-Length': str(os.path.getsize(filename)),
        'Content-Disposition': 'attachment'
    })
    await resp.prepare(request)
    with open(filename, 'rb') as f:
        resp.write(f.read())
    return resp


def text_file_response(filename):
    with open(filename) as f:
        return web.Response(body=f.read().encode(), headers={
            'Content-Type': 'text/plain',
            'Content-Disposition': 'inline'
        })


def html_response(filename):
    with open(filename) as f:
        return web.Response(body=f.read().encode(), headers={
            'Content-Type': 'text/html'
        })


def directory_response(filename):
    if os.path.exists(os.path.join(filename, 'index.html')):
        return html_response(os.path.join(filename, 'index.html'))
    return web.Response(body=directory_listing_body(filename).encode(),
                        headers={'Content-Type': 'text/html'})


def filetype_fallback(filename):
    if 'text' in str(subprocess.Popen(['file', filename], stdout=subprocess.PIPE).stdout.read()):
        return 'text/plain'
    else:
        return 'octet/stream'


async def handle(request):
    filename = str(request.rel_url)[1:]
    if filename == 'favicon.ico':
        return web.Response()
    if not os.path.exists(os.path.normpath(filename)):
        return web.Response(status=404)
    if os.path.isdir(os.path.normpath(filename)):
        return directory_response(filename)
    filetype = mimetypes.guess_type(filename)[0]
    if not filetype:
        filetype = filetype_fallback(filename)
    if 'text' in filetype:
        return text_file_response(filename)
    else:
        return await binary_file_response(filename, filetype, request)


def configure_logger(filename):
    logging.basicConfig(filename=filename, level=logging.DEBUG)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logger = logging.getLogger('')
    logger.addHandler(console)
    return logger


def parse_argv():
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help='use given port', type=int)
    parser.add_argument('-s', '--ssl', nargs=2, help='use SSL', metavar=('CERT', 'KEY'))
    return parser.parse_args()


def create_ssl_context(ssl_args):
    if not ssl:
        return None
    context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(ssl_args[0], keyfile=ssl_args[1])
    return context


def main(argv):
    context = None
    args = parse_argv()
    log = configure_logger(os.path.join(os.path.dirname(sys.argv[0]), 'log'))
    app = web.Application(logger=log)
    app.router.add_get('/{tail:.*}', handle)
    web.run_app(app, port=args.port, ssl_context=create_ssl_context(args.ssl))


if __name__ == '__main__':
    pwd = os.path.dirname(sys.argv[0])
    main(sys.argv[1:])
