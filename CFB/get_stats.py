#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: get_stats.py
Author: zlamberty
Created: 2015-11-01

Description:
    make sure that all necessary stats are downloaded

Usage:
    <usage>

"""

import argparse
import logging
import logging.config
import os
import yaml


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

HERE = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger("get_stats.py")
LOGCONF = os.path.join(HERE, 'logging.yaml')
with open(LOGCONF, 'rb') as f:
    logging.config.dictConfig(yaml.load(f))


# ----------------------------- #
#   Main routines               #
# ----------------------------- #

def cfbstats(ystart, yend):
    """ download stats available from cfbstats.com for years (ystart, yend) """
    pass


# ----------------------------- #
#   Command line                #
# ----------------------------- #

def parse_args():
    """ Take a log file from the commmand line """
    parser = argparse.ArgumentParser()
    parser.add_argument("-x", "--xample", help="An Example", action='store_true')

    args = parser.parse_args()

    logger.debug("arguments set to {}".format(vars(args)))

    return args


if __name__ == '__main__':

    args = parse_args()

    main()
