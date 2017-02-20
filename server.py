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


async def handle(request):
    filename = str(request.rel_url)[1:]
    if filename == 'favicon.ico':
        return web.Response()
    if os.path.isdir(os.path.normpath(filename)):
        return web.Response(body=directory_listing_body(filename).encode(),
                            headers={'Content-Type': 'text/html'})
    filetype = mimetypes.guess_type(filename)[0]
    if not filetype:
        if 'text' in str(subprocess.Popen(['file', filename], stdout=subprocess.PIPE).stdout.read()):
            filetype = 'text/plain'
        else:
            filetype = 'octet/stream'
    if 'text' in filetype:
        return web.Response(body=open(filename).read().encode(), headers={
            'Content-Type': 'text/plain',
            'Content-Disposition': 'inline'
        })
    else:
        resp = web.StreamResponse(headers={
            'Content-Type': filetype,
            'Content-Length': str(os.path.getsize(filename)),
            'Content-Disposition': 'attachment'
        })
        await resp.prepare(request)
        resp.write(open(filename, 'rb').read())
        return resp


def configure_logger(filename):
    logging.basicConfig(filename=filename, level=logging.DEBUG)
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    logger = logging.getLogger('')
    logger.addHandler(console)
    return logger


def main(argv):
    context = None
    parser = argparse.ArgumentParser()
    parser.add_argument('-p', '--port', help='use given port', type=int)
    parser.add_argument('-s', '--ssl', nargs=2, help='use SSL', metavar=('CERT', 'KEY'))
    parser.add_argument('-t', '--passwd', help='use given passphrase (SSL)')
    args = parser.parse_args()
    log = configure_logger(os.path.join(os.path.dirname(sys.argv[0]), 'log'))
    if args.ssl:
        context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(args.ssl[0], keyfile=args.ssl[1], password=args.passwd)
    app = web.Application(logger=log)
    app.router.add_get('/{tail:.*}', handle)
    web.run_app(app, port=args.port, ssl_context=context)


if __name__ == '__main__':
    pwd = os.path.dirname(sys.argv[0])
    main(sys.argv[1:])
