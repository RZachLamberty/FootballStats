#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: game_results_history.py
Author: zlamberty
Created: 2015-11-01

Description:
    download historical results of games

Usage:
    <usage>

"""

import argparse
import cPickle as pickle
import json
import logging
import logging.config
import os
import requests
import time
import yaml

from collections import defaultdict
from itertools import product
from lxml import html, etree


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

URL = "http://espn.go.com/college-football/scoreboard/_/group/80/year/{year:}/seasontype/2/week/{week:}"
HERE = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(HERE, 'data')
F_RES = os.path.join(
    DATA_DIR, 'results.y0_{ystart:}.y1_{yend:}.w0_{wstart:}.w1_{wend:}.pkl'
)
logger = logging.getLogger("result_history")
LOGCONF = os.path.join(HERE, 'logging.yaml')
with open(LOGCONF, 'rb') as f:
    logging.config.dictConfig(yaml.load(f))


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

class ResultHistory(object):
    """ virtual class """
    def __init__(self):
        raise NotImplementedError()

    def get_results(self):
        raise NotImplementedError()


class EspnResultHistory(ResultHistory):
    """ iterate through the espn results pages, parsing each page """
    def __init__(self, url=URL, ystart=2002, yend=2015, wstart=1, wend=15, fres=F_RES):
        self.url = url
        self.ystart = ystart
        self.yend = yend
        self.wstart = wstart
        self.wend = wend
        self.fres = fres.format(
            ystart=self.ystart,
            yend=self.yend,
            wstart=self.wstart,
            wend=self.wend,
        )
        self.results = []

    def load_results(self, forceReload=False):
        """ retrun df of results """
        if os.access(self.fres, os.R_OK) and not forceReload:
            with open(self.fres, 'rb') as f:
                self.results = pickle.load(f)
        else:
            for (y, w, url) in self.espn_result_urls():
                # it seems like espn is rate limiting; pause to play nice maybe?
                time.sleep(0.5)
                try:
                    self.update_from_url(url, y, w)
                except IndexError:
                    # just wait a half second and try again?
                    self.update_from_url(url, y, w)
            self.save_results()

    def espn_result_urls(self):
        """ generater of espn result urls """
        years = range(self.ystart, self.yend + 1)
        weeks = range(self.wstart, self.wend + 1)
        for (y, w) in product(years, weeks):
            yield y, w, self.url.format(year=y, week=w)

    def update_from_url(self, url, y, w):
        try:
            logging.info('loading {}'.format(url))
            resp = requests.get(url)
            x = html.fromstring(resp.text)

            # this is so bootleg...
            scripts = x.xpath('head/script')
            sbdata = [
                s.text for s in scripts
                if s.text
                and s.text.startswith('window.espn.scoreboardData')
            ][0]
            sbdata = sbdata.replace('window.espn.scoreboardData \t= ', '')
            sbdata = sbdata[:sbdata.find(';window.espn')]
            sbdata = json.loads(sbdata)

            for event in sbdata['events']:
                gameres = {}
                gamesum = event['competitions'][0]

                gameres['is_neutral_site'] = gamesum['neutralSite']
                gameres['year'] = y
                gameres['week'] = w

                teams = gamesum['competitors']
                for (i, team) in enumerate(teams):
                    tabbr = team['team']['abbreviation']
                    pts = int(team['score'])
                    gameres['team_{}'.format(i)] = tabbr
                    gameres['team_{}_full'.format(i)] = team['team']['displayName']
                    gameres['team_{}_pts'.format(i)] = pts

                    if team['winner']:
                        gameres['winning_team'] = tabbr
                    else:
                        gameres['losing_team'] = tabbr

                    if team['homeAway'] == 'home':
                        gameres['home_team'] = tabbr

                self.results.append(gameres)
        except Exception as e:
            logging.info("unplanned exception for url {}".format(url))
            logging.error("error message: {}".format(e))
            raise

    # saving / re-loading pkl files
    def save_results(self):
        with open(self.fres, 'wb') as f:
            pickle.dump(self.results, f)
