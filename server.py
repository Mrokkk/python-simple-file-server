#!/bin/env python3

from aiohttp import web
import os

async def handle(request):
    filename = '.' + str(request.rel_url)
    print('Handling: ' + filename)
    if filename == './favicon.ico':
        return web.Response()
    if os.path.isdir(filename):
        return web.Response(body=get_directory_listing(filename).encode(), headers={'Content-Type': 'text/html'})
    f = open(filename)
    if filename.endswith('.html'):
        headers = {'Content-Type': 'text/html'}
    elif filename.endswith('.tar.gz'):
        headers = {'Content-Type': 'application/octet-stream'}
    else:
        headers = {'Content-Type': 'text/plain', "Content-Disposition": "inline"}
    return web.Response(body=f.read().encode(), headers=headers)


def human_readable_size(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)


def get_directory_listing(dirname):
    body = """\
<!DOCTYPE html>
<html>
<title>
   Shared
</title>
<h1>
   Directory listing {}
</h1>
<hr>
<table>
    <th align=left>
        Name
    </th>
    <th style="padding-left: 20pt;">
        Type
    </th>
    <th style="padding-left: 20pt;">
        Size
    </th>""".format(dirname.replace('.', ''))
    for filename in os.listdir(dirname):
        if filename.startswith('.'): # Don't show hidden files
            break
        fullpath = dirname  + '/' + filename
        if os.path.isdir(fullpath):
            file_type='Dir'
        else:
            file_type='File'
        if dirname != './':
            filename = '/' + filename
        dir = dirname.replace('./', '')
        body += """
    <tr>
        <td>
            <a href={}>{}</a>
        </td>
        <td style="padding-left: 20pt;">
            {}
        </td>
        <td style="padding-left: 20pt;">
            {}
        </td>
    </tr>""".format(dir + filename, dir + filename, file_type, human_readable_size(os.path.getsize(fullpath)))
    body += """
<table>
<hr>
</html>"""
    return body


app = web.Application()
app.router.add_get('/{tail:.*}', handle)

web.run_app(app)

