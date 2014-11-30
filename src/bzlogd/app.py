#!/usr/bin/python
# -*- coding: utf-8 -*-
"""bzlogd.app module.

.. moduleauthor:: Jan Milík <milikjan@fit.cvut.cz>
"""


import SimpleHTTPServer
import SocketServer
import sqlite3
import logging
import urlparse
import cgi
import time

import mlabutils.app


class LogStorage(object):
    def __init__(self, file_name = ":memory:"):
        self.db = sqlite3.connect(file_name)

        self.db.execute("""
            CREATE TABLE IF NOT EXISTS query_log (
                server_time INTEGER,
                entry_time INTEGER,
                station TEXT,
                level TEXT,
                event TEXT,
                message TEXT
            )
        """)
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS stations (
                name TEXT,
                last_upload INTEGER,
            )
        """)
        self.db.commit()

    def log_query(self, message, **kwargs):
        t = time.time()

        self.db.execute(
            """INSERT INTO query_log VALUES (?, ?, ?, ?, ?, ?)""",
            (
                t,
                kwargs.get("time", None),
                station,
                kwargs.get("level", None),
                kwargs.get("event", None),
                str(message),
            )
        )
        self.db.commit()

    def get_log_entries(self):
        cursor = self.db.cursor()
        cursor.execute(
            """SELECT station, message FROM query_log"""
            )
        return cursor.fetchall()


PORT = 8080


class HTTPHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.query = urlparse.urlparse(self.path)

        try:
            self.server.storage.log_query(self.path)

            self.wfile.write("<html>\n")
            self.wfile.write("<body>\n")
            self.wfile.write("<h1>Bolidozor Log Server</h1>\n")

            self.wfile.write(
                "<pre>%r</pre>\n" % (self.query, ))

            self.wfile.write("<table>\n")
            for station, query in self.server.storage.get_queries():
                self.wfile.write(
                    "<tr><td><pre>%s</pre></td><td><pre>%s</pre></td></tr>" % (
                            station,
                            query,
                        )
                    )
            self.wfile.write("</table>\n")

            self.wfile.write("</body>\n")
            self.wfile.write("</html>\n")
        except Exception as e:
            self.server.logger.exception(
                "Exception occured while handling request from %s: %s.",
                self.client_address, self.path)

    def do_POST(self):
        try:
            self.parsed_url = urlparse.urlparse(self.path)

            path = self.parsed_url.path
            if not path.startswith("/"):
                path = "/" + path

            method = {
                "/log": self._handle_log,
            }.get(path, None)
        except Exception as e:
            self.server.logger.exception(
                "Exception occured while routing POST request from %s to %s.",
                self.client_address,
                self.path)
            self.send_response(500, "Internal server error.")
            return

        try:
            self.query = urlparse.urlparse(self.path)
            self.server.logger.info("POST query: %r", self.query)

            if self.query.path not in ("/log", "log"):
                self.server.logger.info("unknown path: %s", self.query.path)
                self.send_error(404, "Page not found.")
                return

            self.server.logger.info("post request to log")

            form = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ={'REQUEST_METHOD':'POST',
                         'CONTENT_TYPE':self.headers['Content-Type'],
                         })

            self.server.logger.info("POST data: %r", form)
            self.server.storage.log_query(repr(form), form.getvalue("station"))

            self.send_response(200, "Ok")
        except Exception as e:
            self.server.logger.exception(
                "Exception occured while handling POST request from %s.",
                self.client_address)

            self.send_repsonse(500, "Internal server error.")

    def log_request(self, code = None, size = None):
        self.log_message(
            "Request from %s: %s",
            self.client_address,
            self.path)

    def log_message(self, format, *args):
        self.server.log_message(format, *args)

    def log_error(self, format, *args):
        self.server.log_error(format, *args)


class HTTPServer(SocketServer.TCPServer):
    def __init__(self, address, logger = None):
        SocketServer.TCPServer.__init__(self, address, HTTPHandler)
        self.storage = LogStorage()

        self.logger = logger
        if logger is None:
            self.logger = logging.getLogger(type(self).__name__)

    def log_error(self, format, *args):
        self.logger.error(format, *args)

    def log_message(self, format, *args):
        self.logger.info(format, *args)


class ServerApp(mlabutils.app.DaemonAppBase):
    def _get_app_name(self):
        return "bzlogd"

    def run_daemon(self):
        httpd = HTTPServer(("", PORT))
        httpd.serve_forever()


def main():
    """Main module function."""

    app = ServerApp()
    app.main()


if __name__ == "__main__":
    main()
