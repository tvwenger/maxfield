#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - branch_bound.py

Branch bound method of function minimzation

GNU Public License
http://www.gnu.org/licenses/
Copyright(C) 2016 by
Jonathan Baker; babamots@gmail.com
Trey Wenger; tvwenger@gmail.com

Determine agent order based on distance

Original by jpeterbacker
29 Sept 2014 - tvw V2.0 major update to new version
26 Feb 2016 - tvw v3.0
              merged some new stuff from jpeterbaker's new version
"""

import numpy as np

class CantSplit(Exception):
    pass

# This could be used if more splits are wanted than are possible
class InfState:
    def __init__(self):
        self.value = np.inf
    def split(self,num):
        raise CantSplit()

def branch_bound(root,lo,hi,callback=None):
    '''
    Uses a branch-and-bound style approach to minimize a function

    hi: maximum number of branches to obtain at each level
    lo: number of branches to explore further
    callback: function called at the beginning of every iteration

    The tree will grow up to 'hi' branches and then be trimmed down to 'lo'

    root: is an instance of a state class with callable split(num)
            create an iterable of functin values "root.values"
        each member of root.children should also be a state class
        members of root.values correspond to members of root.children

    returns s,v (the state and lowest found value)
    '''
    if callback == None:
        def callback():
            pass

    # number of branches to make from each branch
    # this number could be different for each branch, e.g. proportional to value
    splitSize = hi // lo

    states = [root]
    finals = [] # Terminating states

    # returns true, if an equivalent state of agents has already been
    # added with a smaller time value
    def isRedundant(candidate, cache):
        # creates a bitmap where a '1' in position 'x' (i.e., 1 << x)
        # means that an agent's last action was to complete
        # the link number 'x' of the plan
        key = sum([1 << i for i in candidate.lastat[-1] if i != None])

        val = state.time[-1]
        try:
            prev = cache[key]
            if val < prev:
                cache[key] = val
                return False
            else:
                return True
        except KeyError:
            cache[key] = val
            return False


    while len(states) > 0:
        callback()

        # The branches of the states
        branches = []
        bestvals = {}

        for state in states:
            try:
                candidates = state.split(splitSize)
                branches.extend([c for c in candidates if not isRedundant(c, bestvals)])
                # print len(branches),'branches'
            except CantSplit:
                finals.append(state)
                break

        branchvalues = [branch.value for branch in branches]
        bestlo = np.argsort(branchvalues)[:lo]
        states = [branches[i] for i in bestlo]


    best = np.argmin([s.value for s in finals])
    # print finals[0].value
    # print finals[-1].value
    return finals[best],finals[best].value

