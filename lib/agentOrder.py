#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - agentOrder.py

Determine agent order based on distance

Original by jpeterbacker
29 Sept 2014 - tvw V2.0 major update to new version
"""
import geometry
import numpy as np

import orderedTSP

# Walking speed in m/s
WALKSPEED = 2
# Seconds it takes to communicate link completion
# Agents should report their consecutive links simultaneously
COMMTIME = 60
# Seconds to create a link
LINKTIME = 15

## DEPRECIATED ##
def getGreedyAgentOrder_DONT_USE_THIS_FUNCTION(a,nagents,orderedEdges):
    '''
    a is a digraph
        node have 'pos' property with location
    nagents is the number of agents
    orderedEdges maps i to the ith edge to be made

    this greedily minimizes wait time (equating distance with time)
    the player who has the most time to spare is assigned the link
    '''
    m = len(orderedEdges)

    # movements[i][j] will be the index (in orderedEdges) of the jth edge that agent i should make
    movements = dict([ (i,[]) for i in range(nagents) ])

    # The ammount of time that has elapsed
    curtime = 0.

    # Last time at which the agents made links
    lastActTime = np.zeros(nagents)
    
    # agent locations
    agentpos = np.empty([nagents,2])

    # Find initial deployments: starts[i] is the agent who starts at node i
    starts = {}
    assigning = 0

    e=0
    for e in xrange(m):
        p = orderedEdges[e][0]
        if not p in starts:
            # Nobody is at this link's head yet
            movements[assigning].append(e)
            starts[p] = assigning
            
            agentpos[assigning] = a.node[p]['geo']

            assigning += 1
            if assigning >= nagents:
                break
        else:
            # the agent who is already at this link's head should make it
            movements[starts[p]].append(e)

    # No agents have actually moved yet

    # continue from startup loop
    for e in xrange(e+1,m):
        p,q = orderedEdges[e]
        ppos = a.node[p]['geo']

        dists = geometry.sphereDist(agentpos,ppos)
        radii = curtime-lastActTime # how far could they have moved
        waits = dists-radii # how long will the team wait if this agent moves
        waits[waits<0] = 0 # no time travel

        mover = np.argmin(waits)
        movements[mover].append(e)

        agentpos[mover] = ppos
        curtime += waits[mover] + linkTime
        lastActTime[mover] = curtime
    
    return movements

def condenseOrder(order):
    '''
    order is a list of integers
    returns (s,mult)
        where
    mult[i] is the multiplicity of a sequence of repeated s[i]'s in order

    EXAMPLE:
        condenseOrder( [0,5,5,5,2,2,3,0] )
            returns
        ( [0,5,2,3,0] , [1,3,2,1,1] )
    '''
    s = []
    mult = []

    cur = order[0]
    count = 0
    for i in order:
        if i == cur:
            # Count the cur's in a row
            count += 1
        else:
            # Add cur and its count to the lists
            s.append(cur)
            mult.append(count)

            # Start counting the new entry
            cur   = i
            count = 1

    # The last sequence never entered the else
    s.append(cur)
    mult.append(count)

    return s,mult

def expandOrder(s,mult):
    '''
    returns a list with s[i] appearing multi[i] times (in place)

    This is the inverse of condenseOrder

    EXAMPLE:
        expandOrder( [0,5,2,3,0] , [1,3,2,1,1] )
            returns
        [0,5,5,5,2,2,3,0]
        
    '''
    m = len(s)
    n = sum(mult)
    order = [None]*n

    writeat = 0
    for i in xrange(m):
        count = mult[i]
        # Put in count occurences of s[i]
        order[writeat:writeat+count] = [s[i]]*count
        writeat += count

    return order

def getAgentOrder(a,nagents,orderedEdges):
    '''
    returns visits
    visits[i] = j means agent j should make edge i
    
    ALSO creates time attributes in a:
        
    Time that must be spent just walking
        a.walktime
    Time it takes to communicate completion of a sequence of links
        a.commtime
    Time spent navigating linking menu
        a.linktime
    '''
    geo = np.array([ a.node[i]['geo'] for i in xrange(a.order())])
    d = geometry.sphereDist(geo,geo)
#    print d
    order = [e[0] for e in orderedEdges]

    # Reduce sequences of links made from same portal to single entry
    condensed , mult = condenseOrder(order)

    link2agent , times = orderedTSP.getVisits(d,condensed,nagents)

    # Expand links made from same portal to original count
    link2agent = expandOrder(link2agent,mult)

    # If agents communicate sequential completions all at once, we avoid waiting for multiple messages
    # To find out how many communications will be sent, we count the number of same-agent link sequences
    condensed , mult = condenseOrder(link2agent)
    numCOMMs = len(condensed)

    # Time that must be spent just walking
    a.walktime = times[-1]/WALKSPEED
    # Waiting for link completion messages to be sent
    a.commtime = numCOMMs*COMMTIME
    # Time spent navigating linking menu
    a.linktime = a.size()*LINKTIME

    movements = [None]*nagents

    for i in xrange(len(link2agent)):
        try:    
            movements[link2agent[i]].append(i)
        except:
            movements[link2agent[i]] = [i]

    return movements

#    m = a.size()
#
#    # link2agent[j] is the agent who makes link j
#    link2agent = [-1]*m
#    for i in range(nagents):
#        for j in movements[i]:
#            link2agent[j] = i
#
#    bestT = completionTime(a,movements)
#
#    sinceImprove = 0
#    i=0
#    while sinceImprove < m:
#        agent = link2agent[i]
#        
#        # for each of the other agents
#        for alt in range(agent-nagents+1,agent):
#
#            alt %= nagents
#            # see what happens if agent 'alt' makes the link
#            link2agent[i] = alt
#
#            T = completionTime(a,link2agent)
#
#            if T < bestT:
#                bestT = T
#                sinceImprove = 0
#                break
#        else:
#            # The loop exited normally, so no improvement was found
#            link2agent[i] = agent # restore the original plan
#            sinceImprove += 1
#
#        i = (i+1)%m
#
#    return movements
#
#
def improveEdgeOrder(a):
    '''
    A greedy algorithm to reduce the path length.
    Moves edges earlier or later, if they can be moved (dependencies are
    done in the proper order) and the move reduces the total length of the
    path.
    The algorithm tries to move 1 to 5 edges at the same time as a block
    to improve upon certain types of local optima.
    '''

    m = a.size()
    # If link i is e then orderedEdges[i]=e
    orderedEdges = [-1]*m

    geo = np.array([ a.node[i]['geo'] for i in xrange(a.order())])
    d = geometry.sphereDist(geo,geo)

    def pathLength(d, edges):
        return sum([d[edges[i][0]][edges[i+1][0]] for i in xrange(len(edges)-1)])

    def dependsOn(subjects, objects):
        '''
        Returns True, if an edge inside 'objects' should be made before
        one (or more) of the edges inside 'subjects'
        '''
        for p,q in subjects:
            depends = a.edge[p][q]['depends']
            for u,v in objects:
                if depends.count((u,v,)) + depends.count(u) > 0:
                    return True

        return False


    def possiblePlaces(j, block):
        '''
        A generator returning the possible places of the given
        block of edges within the complete edge sequence.
        The current position (j) is not returned.
        '''
        pos = j
        # smaller index means made earlier
        while pos > 0 and not dependsOn(block, [orderedEdges[pos-1]]):
            pos -= 1
            yield pos

        pos = j
        bsize = len(block)
        n = len(orderedEdges) - bsize + 1
        # bigger index means made later
        while pos < n-1 and not dependsOn([orderedEdges[pos+bsize]], block):
            pos += 1
            yield pos


    for p,q in a.edges_iter():
        orderedEdges[a.edge[p][q]['order']] = (p,q)

    origLength = pathLength(d, orderedEdges)
    bestLength = origLength

    cont = True
    while cont:
        cont = False
        for j in xrange(m):
            best = j
            bestPath = orderedEdges

            # max block size is 5 (6-1); chosen arbitrarily
            for block in xrange(1, 6):
                moving = orderedEdges[j:j+block]
                for possible in possiblePlaces(j, moving):
                    if possible < j:
                        # Move the links to be at an earlier index
                        path = orderedEdges[   :possible] +\
                                    moving +\
                                    orderedEdges[possible  :j] +\
                                    orderedEdges[j+block: ]
                    else:
                        # Move to a later position
                        path = orderedEdges[   :j] +\
                                    orderedEdges[j+block: possible+block] +\
                                    moving +\
                                    orderedEdges[possible+block  :]

                    length = pathLength(d,path)

                    if length < bestLength:
                        #print("Improved by %f meters in index %d (from %d, block %d)" % (bestLength-length, possible, best, block))
                        best = possible
                        bestLength = length
                        bestPath = path

            if best != j:
                #print("New order (%d -> %d): %s" % (j, best, bestPath))
                orderedEdges = bestPath
                cont = True

    length = pathLength(d, orderedEdges)
    print("Length reduction: original = %d, improved = %d, change = %d meters" % (origLength, length, length-origLength))

    for i in xrange(m):
        p,q = orderedEdges[i]
        a.edge[p][q]['order'] = i


if __name__=='__main__':
    order = [0,5,5,5,2,2,1,0]
#    order = [5]*5
    s,mult = condenseOrder(order)
    print s
    print mult
    print order
    print expandOrder(s,mult)
'''
== Jonathan: maxfield $ python makePlan.py 4 almere/lastPlan.pkl almere/
Total time: 1357.37352334
== Jonathan: maxfield $ python makePlan.py 5 almere/lastPlan.pkl almere/
Total time: 995.599917771
== Jonathan: maxfield $ python makePlan.py 6 almere/lastPlan.pkl almere/
Total time: 890.389138077
== Jonathan: maxfield $ python makePlan.py 7 almere/lastPlan.pkl almere/
Total time: 764.127789228
== Jonathan: maxfield $ python makePlan.py 8 almere/lastPlan.pkl almere/
Total time: 770.827639967
'''
