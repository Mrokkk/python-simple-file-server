#!/bin/env python3

from aiohttp import web
import os

async def handle(request):
    filename = '.' + str(request.rel_url)
    print(filename)
    if os.path.isdir(filename):
        return web.Response(body=handle_dir(filename).encode(), headers={'Content-Type': 'text/html'})
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


def handle_dir(dirname):
    f = \
        '<!DOCTYPE html>\n' \
        '<html>\n' \
        '<title>\n' \
        '   Shared\n' \
        '</title>\n' \
        '<h1>\n' \
        '   Directory listing {}\n' \
        '</h1>\n'.format(dirname.replace('.', ''))
    f += '<hr><table><th align=left>Name</th><th style="padding-left: 20pt;"=left>Type</th><th style="padding-left: 20pt;">Size</th>'
    for filename in os.listdir(dirname):
        if not filename.startswith('.'):
            fullpath = dirname  + '/' + filename
            if os.path.isdir(fullpath):
                file_type='Dir'
            else:
                file_type='File'
            if dirname != './':
                filename = '/' + filename
            dir = dirname.replace('./', '')
            f += '<tr>\n' \
                '   <td>\n' \
                '       <a href={}>{}</a>\n' \
                '   </td>\n' \
                '   <td style="padding-left: 20pt;">\n' \
                '       {}\n' \
                '   </td>\n' \
                '   <td style="padding-left: 20pt;">\n' \
                '       {}\n' \
                '   </td>\n' \
                '</tr>\n'.format(dir + filename, dir + filename, file_type, human_readable_size(os.path.getsize(fullpath)))
    f += '<table><hr></html>'
    return f


app = web.Application()
app.router.add_get('/{tail:.*}', handle)

web.run_app(app)

