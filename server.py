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
import glob
import re

html_head = """<!DOCTYPE html>
<html>
<title>$title</title>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css">
<script src="https://ajax.googleapis.com/ajax/libs/jquery/3.1.1/jquery.min.js"></script>
<script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/js/bootstrap.min.js"></script>
<link rel="stylesheet" href="//cdnjs.cloudflare.com/ajax/libs/jasny-bootstrap/3.1.3/css/jasny-bootstrap.min.css">
<script src="//cdnjs.cloudflare.com/ajax/libs/jasny-bootstrap/3.1.3/js/jasny-bootstrap.min.js"></script>
<style>
* {
    padding:0;
    margin:0;
}
body {
    color: #333;
    font: 14px Sans-Serif;
    padding: 20px;
    background: #eee;
}
</style>
</head>
<div class="container-fluid">
<h1>$title</h1>
</div>
<hr>
<div class="container-fluid">
<form>
    <input type="text" class="form-control" name="search" placeholder="Search...">
</form>
</div>
<div class="container-fluid">
<table data-link="row" class="table table-hover table-condensed">
    <thead>
    <tr>
        <th align="left">Name</th>
        <th style="padding-left: 20pt;">Size</th>
        <th style="padding-left: 20pt;">Modification date</th>
    </tr>
    </thead>
    <tbody>"""

html_foot = """</tbody></table>
</div>
<hr>
</html>"""

filename_entry = """
    <tr>
        <td width="40%"><i class="glyphicon $class_name"></i> <a href="$link">$filename</a></td>
        <td style="padding-left: 20pt;" width="30%">$size</td>
        <td style="padding-left: 20pt;" width="30%">$mtime</td>
    </tr>
"""


def human_readable_size(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Pi', suffix)


def list_file_entries(file_list, dirname):
    body = ''
    for filename in file_list:
        realpath = os.path.join(dirname, filename)
        is_dir = True if os.path.isdir(realpath) else False
        size = '&ltdirectory&gt' if is_dir else human_readable_size(os.path.getsize(realpath))
        link_path = '/' + os.path.relpath(realpath, os.getcwd())
        body += string.Template(filename_entry).substitute(
            link=link_path,
            filename=filename,
            mtime=time.ctime(os.path.getmtime(realpath)),
            size=size,
            class_name='glyphicon-folder-close' if is_dir else 'glyphicon-file')
    return body


def directory_listing_body(dirname):
    body = string.Template(html_head).substitute(title='Directory listing /' + dirname)
    real_dirname = os.path.join(os.getcwd(), dirname)
    list = os.listdir(real_dirname)
    list.insert(0, '..')
    body += list_file_entries(list, real_dirname)
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


def search_result_body(dirname, name):
    body = string.Template(html_head).substitute(title='Search result for "' + name + '"')
    real_dirname = os.path.join(os.getcwd(), dirname)
    file_list = [file for file in glob.glob(os.path.join(dirname, '**/*'), recursive=True)]
    list = [file for file in file_list if name.lower() in file.lower()]
    if dirname != '':
        list = map(str, list)
        list = map(lambda x: x.replace(dirname + '/', ''), list)
    body += list_file_entries(list, real_dirname)
    body += html_foot
    return body


def query_handle_response(filename, query_string):
    query = query_string.split('=')
    if query[0] == 'search':
        return web.Response(body=search_result_body(filename, query[1]).encode(),
                            headers={'Content-Type': 'text/html'})
    return web.Response(status=405)


async def handle(request):
    filename = str(request.path)[1:]
    query_string = str(request.query_string)
    if query_string != '':
        return query_handle_response(filename, query_string)
    if filename == 'favicon.ico':
        with open(os.path.join(os.path.dirname(sys.argv[0]), 'icons/favicon.ico'), 'rb') as f:
            return web.Response(body=f.read(), headers={
                    'Content-Type': 'image/x-icon'
                })
    if not os.path.exists(os.path.normpath(filename)):
        return web.Response(status=404)
    if os.path.isdir(os.path.normpath(filename)):
        return directory_response(filename)
    if filename.endswith('.html'):
        return html_response(filename)
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
    if not ssl_args:
        return None
    context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
    try:
        context.load_cert_chain(ssl_args[0], keyfile=ssl_args[1])
    except Exception as exc:
        print('Error: {}'.format(exc))
        print('Starting without SSL')
        return None
    return context


def main():
    args = parse_argv()
    log = configure_logger(os.path.join(os.path.dirname(sys.argv[0]), 'log'))
    app = web.Application(logger=log)
    app.router.add_get('/{tail:.*}', handle)
    web.run_app(app, port=args.port, ssl_context=create_ssl_context(args.ssl))


if __name__ == '__main__':
    main()
