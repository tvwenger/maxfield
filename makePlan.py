#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - makePlan.py

GNU Public License
http://www.gnu.org/licenses/
Copyright(C) 2016 by
Jonathan Baker; babamots@gmail.com
Trey Wenger; tvwenger@gmail.com

Maxfield is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Maxfield is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Maxfield.  If not, see <http://www.gnu.org/licenses/>.

Original version by jpeterbaker
22 July 2014 - tvw updates csv file format
15 August 2014 - tvw updates with google API, adds -s,
                 switchted to ; delimited file
29 Sept 2014 - tvw V2.0 major update to new version
21 April 2015 - tvw V2.1 force data read to be string
26 Feb 2016 - tvw v3.0
              merged some new stuff from jpeterbaker's new version
02 Mar 2016 - tvw v3.1
              added option to skip link-by-link plots
              added timeout
"""

import sys
import os
import argparse
import networkx as nx
import numpy as np
import pandas as pd
from lib import maxfield,PlanPrinterMap,geometry,agentOrder
import pickle
import copy
import time
from pebble import process, TimeoutError # to handle timeout
import json

import matplotlib.pyplot as plt

# version number
_V_ = '3.1.0'
# max portals allowed
_MAX_PORTALS_ = 500
# number of attempts to try to get best plan
_NUM_ATTEMPTS = 100

def main(args):
    start_time = time.time()
    if args.log is not None:
        sys.stdout = open(args.log,'w',0)
    GREEN = '#3BF256' # Actual faction text colors in the app
    BLUE  = '#2ABBFF'
    if args.res:
        color=BLUE
    else:
        color=GREEN
    # Use google?
    useGoogle = args.google
    api_key = args.api_key

    output_directory = args.output_dir
    # add ending separator
    if output_directory[-1] != os.sep:
        output_directory += os.sep
    # create directory if doesn't exist
    if not os.path.isdir(output_directory):
        os.mkdir(output_directory)
    output_file = args.output_file
    if output_file[-4:] != '.pkl':
        output_file += ".pkl"

    nagents = args.num_agents
    if nagents <= 0:
        print "Number of agents should be greater than zero"
        raise ValueError("Number of agents should be greater than zero")

    input_file = args.input_file

    if input_file[-3:] != 'pkl':
        # If the input file is a portal list, let's set things up
        a = nx.DiGraph() # network tool
        locs = [] # portal coordinates
        # each line should be name;intel_link;keys
        portals = pd.read_table(input_file,sep=';',
                                comment='#',index_col=False,
                                names=['name','link','keys','sbla'],
                                dtype=str)
        portals = np.array(portals)
        portals = np.array([portal for portal in portals if (isinstance(portal[0], basestring) and isinstance(portal[1], basestring))])
        print "Found {0} portals in portal list.".format(len(portals))

        intel_url = "https://www.ingress.com/intel?z=17&" # setup url for intel map
        ll_set = False
        pls = []

        if len(portals) < 3:
            print "Error: Must have more than 2 portals!"
            raise ValueError("Error: Must have more than 2 portals!")
        if len(portals) > _MAX_PORTALS_:
            print "Error: Portal limit is {0}".format(_MAX_PORTALS_)
            raise ValueError("Error: Portal limit is {0}".format(_MAX_PORTALS_))
        for num,portal in enumerate(portals):
            if len(portal) < 3:
                print "Error! Portal ",portal[0]," has a formatting problem."
                raise ValueError("Error! Portal ",portal[0]," has a formatting problem.")
            # loop over columns. Four possibilities:
            # 0. First entry is always portal name
            # 1. contains "pll=" it is the Intel URL
            # 2. contains an intenger, it is the number of keys
            # 3. contains "sbla", it is an SBLA portal
            loc = None
            keys = 0
            sbla = False
            for pind,pfoobar in enumerate(portal):
                if str(pfoobar) == 'nan':
                    continue
                if pind == 0: # This is the name
                    a.add_node(num)
                    a.node[num]['name'] = pfoobar.strip()
                    continue
                if 'pll=' in pfoobar: # this is the URL
                    if loc is not None:
                        print "Error! Already found URL for this portal: {0}".format(portal[0])
                        raise ValueError("Error! Already found URL for this portal: {0}".format(portal[0]))
                    coords = (pfoobar.strip().split('pll='))
                    if len(coords) < 2:
                        print "Error! Portal ",portal[0]," has a formatting problem."
                        raise ValueError("Error! Portal ",portal[0]," has a formatting problem.")
                    coord_parts = coords[1].split(',')
                    lat = int(float(coord_parts[0]) * 1.e6)
                    lon = int(float(coord_parts[1]) * 1.e6)
                    pls.append(coord_parts[0] + "," + coord_parts[1])
                    loc = np.array([lat,lon],dtype=float)
                    if not ll_set:
                        # use coordinates from first portal to center the map
                        intel_url += "ll=" + coord_parts[0] + "," + coord_parts[1] + "&"
                        ll_set = True
                    continue
                try: # this is the number of keys
                    keys = int(pfoobar.strip())
                    continue
                except ValueError:
                    pass
                try: # this is SBLA
                    sbla = pfoobar.strip()
                    sbla = (sbla.lower() == 'sbla')
                    continue
                except ValueError:
                    pass
                # we should never get here unless there was a bad column
                print "Error: bad data value here:"
                print portal
                print pfoobar
                raise ValueError()
            if loc is None:
                print "Formatting problem: {0}".format(portal[0])
                raise ValueError("Formatting problem: {0}".format(portal[0]))
            locs.append(loc)
            a.node[num]['keys'] = keys
            a.node[num]['sbla'] = sbla
            if sbla:
                print "{0} has SBLA".format(portal[0])

        n = a.order() # number of nodes
        locs = np.array(locs,dtype=float)

        # Convert coords to radians, then to cartesian, then to
        # gnomonic projection
        locs = geometry.LLtoRads(locs)
        xyz  = geometry.radstoxyz(locs)
        xy   = geometry.gnomonicProj(locs,xyz)

        for i in xrange(n):
            a.node[i]['geo'] = locs[i]
            a.node[i]['xyz'] = xyz[i]
            a.node[i]['xy' ] = xy[i]

        # build portal list for intel_url
        intel_url += "pls="
        json_output = []
        for p in xrange(len(pls)):
            if p < len(pls) - 1:
                intel_url += pls[p] + "," + pls[p+1]
                intel_url += "_"
                json_output.append({"type":"polyline", "latLngs":
                    [ { "lat": pls[p].split(',')[0],   "lng": pls[p].split(',')[1] },
                      { "lat": pls[p+1].split(',')[0], "lng": pls[p+1].split(',')[1] }
                    ],
                    "color": "#a24ac3"})
            elif p == len(pls)-1:
                intel_url += pls[p] + "," + pls[0]
                json_output.append({"type":"polyline", "latLngs":
                    [ { "lat": pls[p].split(',')[0], "lng": pls[p].split(',')[1] },
                      { "lat": pls[0].split(',')[0], "lng": pls[0].split(',')[1] }
                    ],
                    "color": "#a24ac3"})
        print intel_url
        print json.dumps(json_output, indent=4)

        # Below is remnants from "random optimization" technique
        """
        # EXTRA_SAMPLES attempts to get graph with few missing keys
        # Try to minimuze TK + 2*MK where
        # TK is the total number of missing keys
        # MK is the maximum number of missing keys for any single
        # portal
        bestgraph = None
        bestlack = np.inf
        bestTK = np.inf
        bestMK = np.inf

        allTK = []
        allMK = []
        allWeights = []

        sinceImprove = 0

        while sinceImprove<EXTRA_SAMPLES:
            b = a.copy()

            sinceImprove += 1

            if not maxfield.maxFields(b):
                print 'Randomization failure\nThe program may work if you try again. It is more likely to work if you remove some portals.'
                continue

            TK = 0
            MK = 0
            for j in xrange(n):
                keylack = max(b.in_degree(j)-b.node[j]['keys'],0)
                TK += keylack
                if keylack > MK:
                    MK = keylack
            
            weightedlack = TK+2*MK

            allTK.append(TK)
            allMK.append(MK)
            allWeights.append(weightedlack)

            if weightedlack < bestlack:
                sinceImprove = 0
                print 'IMPROVEMENT:\n\ttotal: %s\n\tmax:   %s\n\tweighted: %s'%\
                       (TK,MK,weightedlack)
                bestgraph = b
                bestlack  = weightedlack
                bestTK  = TK
                bestMK  = MK
            else:
                print 'this time:\n\ttotal: %s\n\tmax:   %s\n\tweighted: %s'%\
                       (TK,MK,weightedlack)

            if weightedlack <= 0:
                print 'KEY PERFECTION'
                bestlack  = weightedlack
                bestTK  = TK
                bestMK  = MK
                break
            # if num agent keys is zero, this code isn't true...
            # if all([ b.node[i]['keys'] <= b.out_degree(i) for i in xrange(n) ]):
            #     print 'All keys used. Improvement impossible'
            #     break

            print '%s tries since improvement'%sinceImprove

        if bestgraph == None:
            print 'EXITING RANDOMIZATION LOOP WITHOUT SOLUTION!'
            print ''
            exit()

        print 'Choosing plan requiring %s additional keys, max of %s from single portal'%(bestTK,bestMK)

        plt.clf()
        plt.scatter(allTK,allMK,c=allWeights,marker='o')
        plt.xlim(min(allTK)-1,max(allTK)+1)
        plt.ylim(min(allMK)-1,max(allMK)+1)
        plt.xlabel('Total keys required')
        plt.ylabel('Max keys required for a single portal')
        cbar = plt.colorbar()
        cbar.set_label('Optimization Weighting (lower=better)')
        plt.savefig(output_directory+'optimization.png')

        a = bestgraph
        """
        with open(output_directory+output_file,'w') as fout:
            pickle.dump(a,fout)
    else:
        with open(input_file,'r') as fin:
            a = pickle.load(fin)

    # Optimize the plan to get shortest walking distance
    best_plan = None
    best_PP = None
    best_time = 1.e9
    for foobar in xrange(args.attempts):
        if not args.quiet:
            tdiff = time.time() - start_time
            hrs = int(tdiff/3600.)
            mins = int((tdiff-3600.*hrs)/60.)
            secs = tdiff-3600.*hrs-60.*mins
            sys.stdout.write("\r[{0:20s}] {1}% ({2}/{3} iterations) : {4:02}h {5:02}m {6:05.2f}s".\
                         format('#'*(20*foobar/args.attempts),
                                100*foobar/args.attempts,
                                foobar,args.attempts,
                                hrs,mins,secs))
        b = copy.deepcopy(a)
        maxfield.maxFields(b,allow_suboptimal=(not args.optimal))
        # Attach to each edge a list of fields that it completes
        # catch no triangulation (bad portal file?)
        try:
            for t in b.triangulation:
                t.markEdgesWithFields()
        except AttributeError:
            print "Error: problem with bestgraph... no triangulation...?"
        agentOrder.improveEdgeOrder(b)
        PP = PlanPrinterMap.PlanPrinter(b,output_directory,nagents,useGoogle=useGoogle,
                                        api_key=api_key,color=color)
        totalTime = b.walktime+b.linktime+b.commtime
        if totalTime < best_time:
            best_plan = b
            best_PP = copy.deepcopy(PP)
            best_time = totalTime


    b = best_plan
    agentOrder.improveEdgeOrderMore(b)

    # Re-run to fix the animations and stars of edges that can be done early
    # (improveEdgeOrderMore may have modified the completion order)
    try:
        first = True
        for t in b.triangulation:
            t.markEdgesWithFields(clean = first)
            first = False
    except AttributeError:
        print "Error: problem with bestgraph... no triangulation...?"


    best_PP = PlanPrinterMap.PlanPrinter(b,output_directory,nagents,useGoogle=useGoogle,
                                    api_key=api_key,color=color)
    best_time = b.walktime+b.linktime+b.commtime


    if not args.quiet:
        tdiff = time.time() - start_time
        hrs = int(tdiff/3600.)
        mins = int((tdiff-3600.*hrs)/60.)
        secs = tdiff-3600.*hrs-60.*mins
        sys.stdout.write("\r[{0:20s}] {1}% ({2}/{3} iterations) : {4:02}h {5:02}m {6:05.2f}s".\
                         format('#'*(20),
                                100,args.attempts,args.attempts,
                                hrs,mins,secs))
        print ""

    # generate plan details and map
    best_PP.keyPrep()
    best_PP.agentKeys()
    best_PP.planMap(useGoogle=useGoogle)
    best_PP.agentLinks()

    if args.check and not best_PP.validatePlan():
        print "The plan contains errors!"
        if not args.optimal:
            print "The errors may be due to not using --optimal."

    # These make step-by-step instructional images
    if not args.skipplot:
        best_PP.animate(useGoogle=useGoogle)
        best_PP.split3instruct(useGoogle=useGoogle)

    print ""
    print ""
    print ""
    print "Found best plan after {0} iterations.".format(args.attempts)
    totalTime = best_plan.walktime+best_plan.linktime+best_plan.commtime
    print "Total time: {0} minutes".format(int(totalTime/60. + 0.5))
    print "Number of portals: {0}".format(best_PP.num_portals)
    print "Number of links: {0}".format(best_PP.num_links)
    print "Number of fields: {0}".format(best_PP.num_fields)
    portal_ap = (125*8 + 500 + 250)*best_PP.num_portals
    link_ap = 313 * best_PP.num_links
    field_ap = 1250 * best_PP.num_fields
    print "AP from portals capture: {0}".format(portal_ap)
    print "AP from link creation: {0}".format(link_ap)
    print "AP from field creation: {0}".format(field_ap)
    print "Total AP: {0}".format(portal_ap+link_ap+field_ap)

    tdiff = time.time() - start_time
    hrs = int(tdiff/3600.)
    mins = int((tdiff-3600.*hrs)/60.)
    secs = tdiff-3600.*hrs-60.*mins
    print "Runtime: {0:02}h {1:02}m {2:05.2f}s".format(hrs,mins,secs)

    plt.close('all')

if __name__ == "__main__":
    description=("Ingress Maxfield - Maximize the number of links "
                 "and fields, and thus AP, for a collection of "
                 "portals in the game Ingress.")
    parser = argparse.ArgumentParser(description=description,
                                     prog="makePlan.py")
    parser.add_argument('-v','--version',action='version',
                        version="Ingress Maxfield v{0}".format(_V_))
    parser.add_argument('-g','--google',action='store_true',
                        help='Make maps with google maps API. Default: False')
    parser.add_argument('-a','--api_key',default=None,type=str,
                        help='Google API key for Google maps. Default: None')
    parser.add_argument('-n','--num_agents',type=int,default='1',
                        help='Number of agents. Default: 1')
    parser.add_argument('input_file',type=str,
                        help="Input semi-colon delimited portal file")
    parser.add_argument('-d','--output_dir',default='',type=str,
                        help="Directory for results. Default: "
                        "this directory")
    parser.add_argument('-f','--output_file',default='plan.pkl',
                        type=str,
                        help="Filename for pickle object. Default: "
                        "plan.pkl")
    parser.add_argument('-o','--optimal',action='store_true',
                        help='Force optimal solution. Default: False')
    parser.add_argument('-r','--res',action='store_true',
                        help='Use resistance colors. Default: False')
    parser.add_argument('--attempts',type=int,default=_NUM_ATTEMPTS,
                        help='Number of iterations to try new plans. Default: 100')
    parser.add_argument('-q','--quiet',action='store_true',
                        help='Do not display status bar. Default: False')
    parser.add_argument('-s','--skipplot',action='store_true',
                        help='Skip the step-by-step plots. Default: False')
    parser.add_argument('--timeout',type=float,default=None,help='Timeout in seconds. Default: None')
    parser.add_argument('-c','--check',action='store_true',
                        help='Validate the plan for algorithm errors. Default: False')
    parser.add_argument('--log',type=str,default=None,help='Log file. Default: print to screen.')
    args = parser.parse_args()
    # Set up job using pebble to handle timeout
    if args.timeout is not None:
        with process.Pool(1) as p:
            job = p.schedule(main,args=(args,),timeout=args.timeout)
        try:
            job.get()
        except TimeoutError:
            if args.log is not None:
                sys.stdout = open(args.log,'a',0)
            print "Timeout error: your plan took longer than {0} seconds to complete. Please try submitting again and/or removing some portals.".format(args.timeout)
    else:
        main(args)
