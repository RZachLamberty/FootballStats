#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
#  downanddistance.py
#
#  Copyright 2013 Zach Lamberty <zach@zach-laptop>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

import collections
import copy
import csv
import os
import pylab
import scipy

#-----------------------#
#   Module constants    #
#-----------------------#
GAME_FILE_FORMAT = os.path.join('./data/{0:}', 'game.csv')
TEAM_FILE_FORMAT = os.path.join('./data/{0:}', 'team.csv')
PLAY_FILE_FORMAT = os.path.join('./data/{0:}', 'play.csv')

#-----------------------#
#   CFB Stat class      #
#-----------------------#

class DownAndDistance(object):
    """A class object to hold various dictionaries of compiled /
    parsed college football data, and access / calculation / plotting
    routines.

    """

    def __init__ (self, years):
        """Class initialiser

        """
        years = [str(el) for el in years]
        self.update_team_dic(years)
        self.update_game_dic(years)
        self.update_play_dic(years)

    def update_team_dic(self, years):
        """Load the team dictionaries

        """
        print 'Loading team info...'
        self.teamDic = collections.defaultdict(dict)
        for year in years:
            print '\tyear = {}'.format(year)
            teamFile = TEAM_FILE_FORMAT.format(year)
            if os.path.isfile(teamFile):
                with open(teamFile, 'rb') as fIn:
                    csvIn = csv.DictReader(fIn, quoting=csv.QUOTE_ALL)
                    for row in csvIn:
                        self.teamDic[int(year)][int(row['Team Code'])] = row['Name']
            else:
                print 'Data file {} for year {} doesn\'t exist'.format(teamFile, year)
        print 'Done.'

    def update_game_dic(self, years):
        """ Look for game information from the years in the "years"
        list and parse them into a member dictionary

        """
        print 'Loading game info...'
        self.gameDic = collections.defaultdict(dict)
        for year in years:
            print '\tyear = {}'.format(year)
            gameFile = GAME_FILE_FORMAT.format(year)
            if os.path.isfile(gameFile):
                with open(gameFile, 'rb') as fIn:
                    csvIn = csv.DictReader(fIn, quoting=csv.QUOTE_ALL)
                    for row in csvIn:
                        try:
                            y = int(year)
                            gc = int(row['Game Code'])
                            ht = self.teamDic[y][int(row['Home Team Code'])]
                            at = self.teamDic[y][int(row['Visit Team Code'])]
                            self.gameDic[y][gc] = {'Home': ht, 'Away': at}
                        except Exception as e:
                            print row
                            raise e
            else:
                print 'Data file {} for year {} doesn\'t exist'.format(gameFile, year)
        print 'Done.'

    def update_play_dic(self, years):
        """ Look for play information from the years in the "years"
        list and parse them into a member dictionary

        """
        print 'Loading play info...'
        self.playDic = collections.defaultdict(dict)
        for year in years:
            print '\tyear = {}'.format(year)
            playFile = PLAY_FILE_FORMAT.format(year)
            if os.path.isfile(playFile):
                with open(playFile, 'rb') as fIn:
                    csvIn = csv.DictReader(fIn, quoting=csv.QUOTE_ALL)
                    rowLast = csvIn.next()
                    for rowNow in csvIn:
                        try:
                            down = rowLast['Down']
                            distance = rowLast['Distance']
                            # Handle kickoffs
                            down = int(down) if down else -1
                            distance = int(distance) if distance else -1
                            key = rowLast['Game Code'], rowLast['Play Number']
                            keepKeys = ['Defense Team Code',
                                        'Clock',
                                        'Period Number',
                                        'Spot',
                                        'Offense Points',
                                        'Defense Points',
                                        'Drive Play',
                                        'Play Type',
                                        'Offense Team Code']
                            playDic = {k: rowLast[k] for k in keepKeys}
                            i = rowLast['Spot']
                            f = rowNow['Spot']
                            i = int(i) if i else 100
                            f = int(f) if f else 100
                            playDic['Result'] = f - i
                            self.playDic[down, distance][key] = playDic
                            rowLast = rowNow
                        except Exception as e:
                            print 'rowLast = {}'.format(rowLast)
                            print 'rowNow = {}'.format(rowNow)
                            raise e
            else:
                print 'Data file {} for year {} doesn\'t exist'.format(playFile, year)
        print 'Done.'

    #   PLOTTING STUFF  #
    def show_me(self, plot_str, const_str=None):
        """A wrapper for a bunch of plotting variables

        """
        if plot_str == 'first and 10 pass or run':
            self.first_and_ten_pass_or_run()
        else:
            pass

    def first_and_ten_pass_or_run(self, returnIt=False):
        """Plot the play choice distribution for first and 10
        plays from any point in the field

        """
        x = {'TOTAL': scipy.zeros(100)}
        for (playKey, row) in self.playDic[1, 10].iteritems():
            pt = row['Play Type']
            if pt not in x:
                x[pt] = scipy.zeros(100)
            x[pt][100 - int(row['Spot'])] += 1
            x['TOTAL'][100 - int(row['Spot'])] += 1

        f = pylab.figure()
        s = f.add_subplot(111)
        for pt in x:
            if pt != 'TOTAL':
                x[pt] = x[pt][:-10] / x['TOTAL'][:-10]
                s.plot(x[pt], label=pt)

        s.legend()
        f.show()

        if returnIt:
            return x

    def play_result_by_spot(self, returnIt=False):
        """Collect the result of plots by play type and ball spot.
        Possibly return a dictionary after plotting

        """
        playTypes = ['RUSH', 'PASS']
        x = {pt: collections.defaultdict(dict) for pt in playTypes}
        
        for (down, distance) in self.playDic:
            for (playKey, row) in self.playDic[down, distance].iteritems():
                pt = row['Play Type']
                if pt in playTypes:
                    sp = 100 - int(row['Spot'])
                    if sp not in x[pt]:
                        x[pt][sp] = []
                    x[pt][sp].append(row['Result'])

        for pt in x:
            for sp in x[pt]:
                x[pt][sp] = -scipy.average(x[pt][sp]), scipy.std(x[pt][sp]) / scipy.sqrt(len(x[pt][sp]))

        zr = scipy.array(x['RUSH'][i][0] for i in range(100))
        zp = scipy.array(x['PASS'][i][0] for i in range(100))
        sr = scipy.array(x['RUSH'][i][1] for i in range(100))
        sp = scipy.array(x['PASS'][i][1] for i in range(100))
        
        f = pylab.figure()
        s = f.add_subplot(111)
        s.errorbar(range(100), zr, sr, label='RUSH', color='blue')
        s.errorbar(range(100), zp, sp, label='PASS', color='green')

        s.legend()
        f.show()

        if returnIt:
            return x


#-----------------------#
#   Main routine        #
#-----------------------#


def main():
    return 0

if __name__ == '__main__':
    main()

