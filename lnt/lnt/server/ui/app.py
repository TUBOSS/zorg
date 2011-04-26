import logging
import logging.handlers
import os
import time

import flask
from flask import current_app
from flask import g

import lnt
import lnt.server.ui.filters
import lnt.server.ui.views

# FIXME: Redesign this.
import lnt.viewer.Config
from lnt.db import perfdbsummary
from lnt.viewer import PerfDB

class Request(flask.Request):
    def __init__(self, *args, **kwargs):
        super(Request, self).__init__(*args, **kwargs)

        self.request_time = time.time()
        self.db = None
        self.db_summary = None

    def elapsed_time(self):
        return time.time() - self.request_time

    # Utility Methods

    def get_db(self):
        if self.db is None:
            self.db = PerfDB.PerfDB(g.db_info.path)

            # Enable SQL logging with db_log.
            #
            # FIXME: Conditionalize on an is_production variable.
            if self.args.get('db_log') or self.form.get('db_log'):
                import logging, StringIO
                g.db_log = StringIO.StringIO()
                logger = logging.getLogger("sqlalchemy")
                logger.addHandler(logging.StreamHandler(g.db_log))
                self.db.engine.echo = True

        return self.db

    def get_db_summary(self):
        return current_app.get_db_summary(g.db_name, self.get_db())

class App(flask.Flask):
    @staticmethod
    def create_standalone(config_path):
        # Construct the application.
        app = App(__name__)

        # Register additional filters.
        lnt.server.ui.filters.register(app)

        # Load the application configuration.
        app.load_config(config_path)

        # Load the application routes.
        app.register_module(lnt.server.ui.views.frontend)
                        
        return app

    def __init__(self, name):
        super(App, self).__init__(name)
        self.start_time = time.time()
        self.db_summaries = {}

        # Override the request class.
        self.request_class = Request

        # Store a few global things we want available to templates.
        self.version = lnt.__version__

    def load_config(self, config_path):
        config_data = {}
        exec open(config_path) in config_data

        self.old_config = lnt.viewer.Config.Config.fromData(
            config_path, config_data)

        self.jinja_env.globals.update(
            app=current_app,
            old_config=self.old_config)

    def get_db_summary(self, db_name, db):
        db_summary = self.db_summaries.get(db_name)
        if db_summary is None or not db_summary.is_up_to_date(db):
            self.db_summaries[db_name] = db_summary = \
                perfdbsummary.PerfDBSummary.fromdb(db)
        return db_summary
