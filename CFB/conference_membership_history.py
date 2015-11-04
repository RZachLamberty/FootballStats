#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: conference_membership_history.py
Author: zlamberty
Created: 2015-10-25

Description:
    download conference membership history to ./data

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

from collections import defaultdict
from itertools import product
from lxml import html, etree


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

URLS = [
    "http://espn.go.com/college-football/standings/_/season/{year:}/group/80",
    "http://espn.go.com/college-football/standings/_/season/{year:}/view/fcs"
]
HERE = os.path.dirname(os.path.realpath(__file__))
DATA_DIR = os.path.join(HERE, 'data')
F_CONF = os.path.join(DATA_DIR, 'conferences.y0_{ystart:}.y1_{yend:}.pkl')
logger = logging.getLogger("conference_membership_history")
LOGCONF = os.path.join(HERE, 'logging.yaml')
with open(LOGCONF, 'rb') as f:
    logging.config.dictConfig(yaml.load(f))


# ----------------------------- #
#   Main routine                #
# ----------------------------- #

class ConferenceHistory(object):
    """ virtual class """
    def __init__(self):
        raise NotImplementedError()

    def get_conferences(self):
        raise NotImplementedError()


class EspnConferenceHistory(ConferenceHistory):
    """ iterate through the espn conferences page, parsing each page """
    def __init__(self, urls=URLS, ystart=2002, yend=2015, fconf=F_CONF):
        self.urls = urls
        self.ystart = ystart
        self.yend = yend
        self.fconf = fconf
        self.conferences = defaultdict(dict)

    def load_conferences(self, forceReload=False):
        """ retrun conferences """
        if os.access(self.fconf, os.R_OK) and not forceReload:
            with open(self.fconf, 'rb') as f:
                self.conferences = pickle.load(f)
        else:
            for url in self.urls:
                for y in range(self.ystart, self.yend + 1):
                    rooturl = url.format(year=y)
                    resp = requests.get(rooturl)
                    x = html.fromstring(resp.text)

                    conftables = x.xpath('//table[@class="standings has-team-logos"]')

                    for conftable in conftables:
                        longcap = conftable.find('caption/span').text
                        teamnames = conftable.xpath('tr/td/a/span/span')
                        teamabbrs = conftable.xpath('tr/td/a/span/abbr')
                        for (fullname, codename) in zip(teamnames, teamabbrs):
                            self.conferences[fullname.text, codename.text][y] = longcap

                        # some teams (ahem TAMU ahem) have no links -- weird.
                        teamnames2 = conftable.xpath('tr/td/span/span')
                        teamabbrs2 = conftable.xpath('tr/td/span/abbr')
                        for (fullname, codename) in zip(teamnames2, teamabbrs2):
                            self.conferences[fullname.text, codename.text][y] = longcap

            # flatten
            self.conferences = [
                {'fullname': fullname, 'codename': codename, 'year': year, 'conf': conf}
                for ((fullname, codename), d) in self.conferences.items()
                for (year, conf) in d.items()
            ]

            self.save_conferences()

    # saving / re-loading pkl files
    def save_conferences(self):
        with open(self.fconf, 'wb') as f:
            pickle.dump(self.conferences, f)
