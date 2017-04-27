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
<head>
<title>$title</title>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<script src="/.static/jquery/jquery.min.js"></script>
<link rel="stylesheet" href="/.static/bootstrap/css/bootstrap.min.css">
<script src="/.static/bootstrap/js/bootstrap.min.js"></script>
<link rel="stylesheet" href="/.static/jasny-bootstrap/css/jasny-bootstrap.min.css">
<script src="/.static/jasny-bootstrap/js/jasny-bootstrap.min.js"></script>
<style>
body {
    color: #333;
    font: 16px Sans-Serif;
    background: #eee;
}
a:hover {
    text-decoration: none;
}
</style>
</head>
<body data-spy="scroll" data-target=".navbar" data-offset="100">
<nav class="navbar navbar-inverse navbar-fixed-top">
    <div class="container">
        <ul class="nav navbar-nav">
            <li>
                <div class="navbar-header">
                    <a class="navbar-brand" href="/">File server</a>
                </div>
            </li>
            <li>
                <form class="navbar-form">
                    <div class="input-group">
                        <input type="text" class="form-control" name="search" placeholder="Search..." style="width: 300px;">
                        <div class="input-group-btn">
                            <button class="btn btn-default" type="submit">
                                <i class="glyphicon glyphicon-search"></i>
                            </button>
                        </div>
                    </div>
                </form>
            </li>
        </ul>
    </div>
</nav>
<div class="container" style="padding-top: 60px;">
<div class="panel panel-default">
<div id="panel-head" class="panel-heading">
    $path_buttons
</div>
<div id="panel-body" class="panel-body" style="padding: 0;">
<table data-link="row" class="table table-hover table-condensed" style="margin-bottom: 0;">
    <tbody>"""

html_foot = """</tbody></table></div></div>
</div>
</body>
</html>"""

filename_entry = """
    <tr>
        <td width="2%" style="vertical-align: middle;">
            <i class="glyphicon $icon"></i>
        </td>
        <td width="38%" style="vertical-align: middle;"><a href="$link">$filename</a></td>
        <td width="30%" style="vertical-align: middle;">$size</td>
        <td width="30%" style="vertical-align: middle;">$mtime</td>
    </tr>
"""

path_button_entry = """<a href=$link role="button" class="btn btn-primary">$dirname</a>
"""


def create_path_buttons(dirname):
    dirname = '/' + dirname
    body = '<div id="path-buttons" class="btn-group">\n'
    body += string.Template(path_button_entry).substitute(link='/', dirname='/')
    body += '</div>\n'
    path = '/'
    for element in dirname.split('/'):
        if element:
            path = os.path.join(path, element)
            body += '<div id="path-buttons" class="btn-group">\n'
            body += string.Template(path_button_entry).substitute(link=path, dirname=element)
            body += '</div>\n'
    return body


def human_readable_size(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Pi', suffix)


def list_file_entries(file_list, dirname):
    body = ''
    for filename in file_list:
        if not os.path.exists(os.path.join(dirname, filename)):
            continue
        realpath = os.path.join(dirname, filename)
        is_dir = os.path.isdir(realpath)
        size = '' if is_dir else human_readable_size(os.path.getsize(realpath))
        link_path = '/' + os.path.relpath(realpath, os.getcwd())
        body += string.Template(filename_entry).substitute(
            link=filename,
            filename=filename,
            mtime=time.strftime("%d-%m-%y %H:%M:%S", time.gmtime(os.path.getmtime(realpath))),
            size=size,
            icon='glyphicon-folder-open' if is_dir else 'glyphicon-file')
    return body


def directory_listing_body(dirname):
    body = string.Template(html_head).substitute(path_buttons=create_path_buttons(dirname), title='Directory listing /' + dirname)
    real_dirname = os.path.join(os.getcwd(), dirname)
    list = [f for f in os.listdir(real_dirname) if not f.startswith('.')]
    list.sort()
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
    body = string.Template(html_head).substitute(path_buttons=create_path_buttons(dirname), title='Search result for "' + name + '"')
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
    if filename.startswith('/'):
        return web.HTTPNotFound()
    query_string = str(request.query_string)
    if query_string != '':
        return query_handle_response(filename, query_string)
    if filename == 'favicon.ico':
        with open(os.path.join(os.path.dirname(sys.argv[0]), 'icons/favicon.ico'), 'rb') as f:
            return web.Response(body=f.read(), headers={
                    'Content-Type': 'image/x-icon'
                })
    if not os.path.exists(os.path.normpath(filename)):
        return web.HTTPNotFound()
    if os.path.isdir(os.path.normpath(filename)):
        if (filename != '' and not filename.endswith('/')):
            return web.HTTPFound(request.path + '/')
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
    app.router.add_static('/.static', os.path.join(os.path.dirname(sys.argv[0]), 'static'))
    app.router.add_get('/{tail:.*}', handle)
    web.run_app(app, port=args.port, ssl_context=create_ssl_context(args.ssl))


if __name__ == '__main__':
    main()
