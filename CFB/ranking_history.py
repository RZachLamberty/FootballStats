#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: ranking_history.py
Author: zlamberty
Created: 2015-10-25

Description:
    download rankings history to ./data

Usage:
    <usage>

"""

import argparse
import cPickle as pickle
import logging
import logging.config
import os
import requests
import time
import yaml

from itertools import product
from lxml import html, etree


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

URL = "http://espn.go.com/college-football/rankings/_/seasontype/2/year/{year:}/week/{week:}"
HERE = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(HERE, 'data')
F_RANK = os.path.join(DATA_DIR, 'rankings.y0_{ystart:}.y1_{yend:}.w0_{wstart:}.w1_{wend:}.pkl')
logging.getLogger('requests').setLevel(logging.INFO)
logger = logging.getLogger("ranking_history")
LOGCONF = os.path.join(HERE, 'logging.yaml')
with open(LOGCONF, 'rb') as f:
    logging.config.dictConfig(yaml.load(f))


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

class RankingHistory(object):
    """ virtual class """
    def __init__(self):
        raise NotImplementedError()

    def get_rankings(self):
        raise NotImplementedError()


class EspnRankingHistory(RankingHistory):
    """ iterate through the espn rankings page, parsing each page """
    def __init__(self, url=URL, ystart=2002, yend=2015, wstart=1, wend=15, frank=F_RANK):
        self.url = url
        self.ystart = ystart
        self.yend = yend
        self.wstart = wstart
        self.wend = wend
        self.frank = frank.format(
            ystart=self.ystart,
            yend=self.yend,
            wstart=self.wstart,
            wend=self.wend,
        )
        self.rankings = []

    def load_rankings(self, forceReload=False):
        """ retrun df of rankings """
        if os.access(self.frank, os.R_OK) and not forceReload:
            with open(self.frank, 'rb') as f:
                self.rankings = pickle.load(f)
        else:
            for (y, w, url) in self.espn_ranking_urls():
                # it seems like espn is rate limiting; pause to play nice maybe?
                time.sleep(0.5)
                self.update_from_url(url, y, w)
            self.save_rankings()

    def espn_ranking_urls(self):
        """ generater of espn ranking urls """
        years = range(self.ystart, self.yend + 1)
        weeks = range(self.wstart, self.wend + 1)
        for (y, w) in product(years, weeks):
            yield y, w, self.url.format(year=y, week=w)

    def update_from_url(self, url, y, w):
        try:
            logging.info('loading {}'.format(url))
            resp = requests.get(url)
            x = html.fromstring(resp.text)

            tabs = x.xpath('//table[@class="rankings has-team-logos"]')
            for tab in tabs:
                ranktype = tab.xpath('caption')[0].text.lower().replace(' ', '_')

                rows = tab.xpath('tbody/tr')

                # start-of-year AP polls are often represented as just 1 team
                # (previous year champion, etc). Can't tell if it's a bug or
                # intentional, but it is definitely not desirable. Example:
                # http://espn.go.com/college-football/rankings/_/seasontype/2/year/2003/week/1
                if len(rows) < 20:
                    continue

                for row in rows:
                    # ties are represented as an empty rank
                    try:
                        rank = int(row.xpath('td/span[@class="number"]')[0].text)
                    except IndexError:
                        rank = lastrank

                    # some teams do not have links but rather spans
                    try:
                        team = row.xpath('td/a/abbr')[0]
                    except:
                        team = row.xpath('td/span/abbr')[0]

                    fullname = team.attrib['title']
                    codename = team.text
                    self.rankings.append({
                        'rank_type': ranktype,
                        'rank': rank,
                        'codename': codename,
                        'fullname': fullname,
                        'year': y,
                        'week': w,
                    })
                    lastrank = rank
        except Exception as e:
            logging.info("unplanned exception for url {}".format(url))
            logging.error("error message: {}".format(e))
            raise

    # saving / re-loading pkl files
    def save_rankings(self):
        with open(self.frank, 'wb') as f:
            pickle.dump(self.rankings, f)
