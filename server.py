#!/bin/env python3

from aiohttp import web
import os
import sys
import getopt
import mimetypes
import time
import subprocess
import ssl


def human_readable_size(num, suffix='B'):
    for unit in ['', 'Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def directory_listing_body(dirname):
    body = """\
<!DOCTYPE html>
<html>
<title>
   Directory listing /{}
</title>
<style>
th {{
    text-align: left;
}}
</style>
<h1>
   Directory listing /{}
</h1>
<hr>
<table>
    <tr>
        <th align="left">Name</th>
        <th style="padding-left: 20pt;">Type</th>
        <th style="padding-left: 20pt;">Modification date</th>
        <th style="padding-left: 20pt;">Size</th>
    </tr>
    """.format(dirname, dirname)
    real_dirname = os.path.join(os.getcwd(), dirname)
    for filename in os.listdir(real_dirname):
        realpath = os.path.join(real_dirname, filename)
        if os.path.isdir(realpath):
            file_type = 'Dir'
        else:
            file_type = 'File'
        link_path = '/' + os.path.relpath(realpath, os.getcwd())
        body += """
    <tr>
        <td>
            <a href="{}">{}</a>
        </td>
        <td style="padding-left: 20pt;">
            {}
        </td>
        <td style="padding-left: 20pt;">
            {}
        </td>
        <td style="padding-left: 20pt;">
            {}
        </td>
    </tr>""".format(link_path,
                    filename,
                    file_type,
                    time.ctime(os.path.getmtime(realpath)),
                    human_readable_size(os.path.getsize(realpath)))
    body += """
<table>
<hr>
</html>"""
    return body


async def handle(request):
    filename = str(request.rel_url)[1:]
    print('Handling: ' + filename)
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


def main(argv):
    port = None
    context = None
    key = None
    cert = None
    password = None
    help = 'server.py -p|--port=<port> -c|--cert=<cert_file> -k|--key=<key_file> -t|--pass=<password>'
    try:
        opts, args = getopt.getopt(argv, "hp:c:k:t:", ["help", "port=", "cert=", "key=", "pass="])
    except getopt.GetoptError:
        print(help)
        sys.exit(1)
    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print(help)
            sys.exit(0)
        elif opt in ('-p', '--port'):
            port = int(arg)
        elif opt in ('-c', '--cert'):
            cert = str(arg)
        elif opt in ('-k', '--key'):
            key = str(arg)
        elif opt in ('-t', '--pass'):
            password = str(arg)
    if key and cert:
        print('Using SSL')
        context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(cert, keyfile=key, password=password)
    app = web.Application()
    app.router.add_get('/{tail:.*}', handle)
    web.run_app(app, port=port, ssl_context=context)


if __name__ == '__main__':
    pwd = os.path.dirname(sys.argv[0])
    main(sys.argv[1:])
