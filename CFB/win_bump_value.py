#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module: win_bump_value.py
Author: zlamberty
Created: 2015-10-25

Description:
    analyze the effect of winning a game on your ranking -- for example, is it
    better to beat an SEC team than a PAC12 team? If so, how much better? What
    factor is most significant in terms of the overall improvement on your
    ranking?

    The operative statistic here will be "bouyancy" -- how high do you rise (how
    many spots / teams / winning teams do you jump) with your win, and  how far
    do you fall with your loss? In particular, is there an imbalance?

TODO:
    clean up the rankings script for the weird ncaa college football power
    rankings (many teams get a 0 ranking, )

Usage:
    <usage>

"""

import argparse
import logging
import logging.config
import os
import pandas as pd
import yaml

import conference_membership_history as cmh
import ranking_history as rh
import game_results_history as grh


# ----------------------------- #
#   Module Constants            #
# ----------------------------- #

HERE = os.path.dirname(os.path.realpath(__file__))
logger = logging.getLogger("win_bump_value.py")
LOGCONF = os.path.join(HERE, 'logging.yaml')
with open(LOGCONF, 'rb') as f:
    logging.config.dictConfig(yaml.load(f))


# ----------------------------- #
#   data acquisition            #
# ----------------------------- #

def get_rankings(reloadRankings=False, reloadConferences=False):
    r = rh.EspnRankingHistory()
    r.load_rankings(forceReload=reloadRankings)
    rankings = pd.DataFrame(r.rankings)

    # drop the 0-rank teams
    rankings = rankings[rankings['rank'] != 0]

    c = cmh.EspnConferenceHistory()
    c.load_conferences(forceReload=reloadConferences)
    conferences = pd.DataFrame(c.conferences)

    # add in conference affiliation
    rankings = rankings.merge(
        conferences[['codename', 'year', 'conf']],
        how='left',
        on=['codename', 'year']
    )

    # UC Davis and North Dakota State conf affiliation aren't available :(
    rankings.loc[
        (rankings.fullname == 'UC Davis') & (rankings.year == 2003), 'conf'
    ] = 'D2 Independent'
    rankings.loc[
        (rankings.fullname == 'UC Davis') & (rankings.year == 2004), 'conf'
    ] = 'Great West Conference'
    rankings.loc[
        rankings.fullname == 'North Dakota State', 'conf'
    ] = 'Great West Conference'

    # ncaa_college_football_power_rankings in 2005 and prior are impossible
    # bullshit to parse
    rankings = rankings[~(
        (rankings.year <= 2005)
        & (rankings.rank_type == 'ncaa_college_football_power_rankings')
    )]

    validate_rankings_data(rankings)

    return rankings


def validate_rankings_data(rankings):
    """ just a holder for all of our data validation steps """
    assert all(rankings.conf.notnull())


def get_game_results(reloadResults=False):
    r = grh.EspnResultHistory()
    r.load_results(forceReload=reloadResults)
    results = pd.DataFrame(r.results)

    # limit only to games that *have* been played and had a winner (ignore ties)
    results = results[results.winning_team.notnull()]

    results.loc[:, 'total_pts'] = results.team_0_pts + results.team_1_pts
    results.loc[:, 'pt_differential'] = (results.team_1_pts - results.team_0_pts).abs()

    validate_results_data(results)

    return results


def validate_results_data(results):
    assert all(results.winning_team.notnull())
    assert all(results.losing_team.notnull())
    assert all(results.losing_team != results.winning_team)


def get_rankings_delta(rankings, results):
    """ re-form the rankings df into a df of rankings week-to-week changes.

        We are tracking:
            1. change in numeric rank
            2. number of teams jumped
            3. number of teams jumped *by*
            4. number of winning teams jumped
            5. number of winning teams jumped *by*

        Because we wish to include information about number of "winning" teams,
        we need to have pre-modified the rankings df with game result
        information. Note that while doing so, we add a column "won" to our
        rankings df. I should point out:
            (not won) != lost
        It could mean that the team lost, or it could also mean they didn't play
        (c.f. almost ever team during week 1 of 2002)

        We make the following assumptions:
            1. For a given ranking system, all unranked teams are equal
            2. Failure to find rankings (i.e. bad data) is equivalent to being
               unranked. So you best get clean data ;)

        Finally, only rely on the codename factor. Others can be null
        (e.g. unranked teams becoming ranked)

    """
    # rankings with wins
    rww = rankings.merge(
        right=results[['year', 'week', 'winning_team']],
        how='left',
        left_on=['year', 'week', 'codename'],
        right_on=['year', 'week', 'winning_team']
    )
    rww.loc[:, 'won'] = rww.winning_team.notnull()

    rankingsDelta = None
    for (y, r) in rww.groupby('year'):
        logger.debug('delta calculation for year = {}'.format(y))
        weeks = r.week.unique()
        for w in weeks:
            wNow = r[r.week == w]
            wNext = r[r.week == (w + 1)][['codename', 'rank', 'rank_type']]

            # skip the last week of the year
            if wNext.empty:
                continue

            wDelta = wNow.merge(
                right=wNext,
                how='outer',
                on=['codename', 'rank_type'],
                suffixes=('_now', '_next')
            )

            # replace all NaN rankings in any ranking type with the maximum
            # values plus 1 (e.g. ap top 25, unranked == 26)
            rt = wDelta.groupby('rank_type')
            replRank = lambda chunk: chunk.fillna(chunk.max() + 1)
            wDelta.loc[:, 'rank_now'] = rt.rank_now.transform(replRank)
            wDelta.loc[:, 'rank_next'] = rt.rank_next.transform(replRank)

            # regular numeric delta
            wDelta.loc[:, 'rank_delta'] = wDelta.rank_now - wDelta.rank_next

            # we rely on the 'won' factor, but the outer merge introduced NaNs
            wDelta.loc[:, 'won'] = wDelta.won.fillna(False)

            # jumping for joy shit
            jumps = wDelta.apply(jump_stats, axis=1, args=(wDelta,))
            wDelta = wDelta.merge(
                right=jumps, how='left', left_index=True, right_index=True
            )

            # merged items could have NaN years or weeks -- fix that easy
            wDelta.loc[:, 'week'] = w
            wDelta.loc[:, 'year'] = y

            if rankingsDelta is None:
                rankingsDelta = wDelta.copy()
            else:
                rankingsDelta = rankingsDelta.append(wDelta)

    return rankingsDelta


def jump_stats(row, wDelta):
    j = jumped(row, wDelta).won
    jb = jumped_by(row, wDelta).won
    return pd.Series({
        'teams_jumped': j.count(),
        'winning_teams_jumped': j.sum(),
        'teams_jumped_by': jb.count(),
        'winning_teams_jumped_by': jb.sum()
    })

def jumped(row, wDelta):
    return wDelta[
        (wDelta.rank_type == row.rank_type)
        & (wDelta.rank_now < row.rank_now)
        & (wDelta.rank_next > row.rank_next)
    ]


def jumped_by(row, wDelta):
    return wDelta[
        (wDelta.rank_type == row.rank_type)
        & (wDelta.rank_now > row.rank_now)
        & (wDelta.rank_next < row.rank_next)
    ]



def week_results(row, results):
    return results[
        (results.year == row.year)
        & (results.week == row.week)
        & (results.winning_team == row.codename)
    ].empty


def better_teams(row, wDelta, rankkey, nonwinners=True):
    return set(
        wDelta.codename[
            (wDelta[rankkey] <= row[rankkey])
            & (nonwinners | (wDelta.won == True))
        ]
    )


def make_buoyancy_df():
    rankings = get_rankings()
    results = get_game_results()

    # add week-to-week changes in rankings information (when available) to the
    # results df
    rww = get_rankings_delta(rankings, results)



# ----------------------------- #
#   Main routine                #
# ----------------------------- #

def main():
    """ docstring """
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
