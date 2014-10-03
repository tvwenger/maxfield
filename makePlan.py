#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - makePlan.py

usage: makePlan.py [-h] [-v] [-g] [-n NUM_AGENTS] [-s SAMPLES] [-d OUTPUT_DIR]
                   [-f OUTPUT_FILE]
                   input_file

Ingress Maxfield - Maximize the number of links and fields, and thus AP, for a
collection of portals in the game Ingress.

positional arguments:
  input_file            Input semi-colon delimited portal file

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -g, --google          Make maps with google maps API. Default: False
  -n NUM_AGENTS, --num_agents NUM_AGENTS
                        Number of agents. Default: 1
  -s SAMPLES, --samples SAMPLES
                        Number of iterations to perform. More iterations may
                        improve results, but will take longer to process.
                        Default: 50
  -d OUTPUT_DIR, --output_dir OUTPUT_DIR
                        Directory for results. Default: this directory
  -f OUTPUT_FILE, --output_file OUTPUT_FILE
                        Filename for pickle object. Default: plan.pkl

Original version by jpeterbaker
22 July 2014 - tvw updates csv file format
15 August 2014 - tvw updates with google API, adds -s,
                 switchted to ; delimited file
29 Sept 2014 - tvw V2.0 major update to new version
"""

import sys
import os
import argparse
import networkx as nx
import numpy as np
import pandas as pd
from lib import maxfield,PlanPrinterMap,geometry,agentOrder
import pickle

import matplotlib.pyplot as plt

# version number
_V_ = '2.0.2'
# max portals allowed
_MAX_PORTALS_ = 50

def main():
    description=("Ingress Maxfield - Maximize the number of links "
                 "and fields, and thus AP, for a collection of "
                 "portals in the game Ingress.")
    parser = argparse.ArgumentParser(description=description,
                                     prog="makePlan.py")
    parser.add_argument('-v','--version',action='version',
                        version="Ingress Maxfield v{0}".format(_V_))
    parser.add_argument('-g','--google',action='store_true',
                        help='Make maps with google maps API. Default: False')
    parser.add_argument('-n','--num_agents',type=int,default='1',
                        help='Number of agents. Default: 1')
    parser.add_argument('-s','--samples',type=int,default=50,
                        help="Number of iterations to "
                        "perform. More iterations may improve "
                        "results, but will take longer to process. "
                        "Default: 50")
    parser.add_argument('input_file',
                        help="Input semi-colon delimited portal file")
    parser.add_argument('-d','--output_dir',default='',
                        help="Directory for results. Default: "
                        "this directory")
    parser.add_argument('-f','--output_file',default='plan.pkl',
                        help="Filename for pickle object. Default: "
                        "plan.pkl")
    args = vars(parser.parse_args())

    # Number of iterations to complete since last improvement
    EXTRA_SAMPLES = args["samples"]

    GREEN = '#3BF256' # Actual faction text colors in the app
    BLUE  = '#2ABBFF'
    # Use google?
    useGoogle = args['google']

    output_directory = args["output_dir"]
    # add ending separator
    if output_directory[-1] != os.sep:
        output_directory += os.sep
    # create directory if doesn't exist
    if not os.path.isdir(output_directory):
        os.mkdir(output_directory)
    output_file = args["output_file"]
    if output_file[-4:] != '.pkl':
        output_file += ".pkl"

    nagents = args["num_agents"]
    if nagents < 0:
        sys.exit("Number of agents should be positive")

    EXTRA_SAMPLES = args["samples"]
    if EXTRA_SAMPLES < 0:
        sys.exit("Number of extra samples should be positive")
    elif EXTRA_SAMPLES > 100:
        sys.exit("Extra samples may not be more than 100")

    input_file = args['input_file']

    if input_file[-3:] != 'pkl':
        # If the input file is a portal list, let's set things up
        a = nx.DiGraph() # network tool
        locs = [] # portal coordinates
        # each line should be name;intel_link;keys
        portals = pd.read_table(input_file,sep=';',
                                comment='#',index_col=False,
                                names=['name','link','keys'],
                                encoding='utf-8')
        print "Found {0} portals in portal list.".format(len(portals))
        if len(portals) > _MAX_PORTALS_:
            sys.exit("Error: Portal limit is {0}".\
                     format(_MAX_PORTALS_))
        for num,portal in enumerate(portals):
            if not isinstance(portal[0], basestring) or portal[0] == "": continue
            a.add_node(num)
            a.node[num]['name'] = portal[0]
            coords = (portal[1].split('pll='))[1]
            coord_parts = coords.split(',')
            lat = int(float(coord_parts[0]) * 1.e6)
            lon = int(float(coord_parts[1]) * 1.e6)
            locs.append(np.array([lat,lon],dtype=float))
            if np.isnan(portal[2]):
                a.node[num]['keys'] = 0
            else:
                a.node[num]['keys'] = int(portal[2])

        n = a.order() # number of nodes
        locs = np.array(locs,dtype=float)

        # Convert coords to radians, then to cartesian, then to
        # gnomonic projection
        locs = geometry.e6LLtoRads(locs)
        xyz  = geometry.radstoxyz(locs)
        xy   = geometry.gnomonicProj(locs,xyz)

        for i in xrange(n):
            a.node[i]['geo'] = locs[i]
            a.node[i]['xyz'] = xyz[i]
            a.node[i]['xy' ] = xy[i]

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
                print 'Randomization failure\nThe program may work if you try again. It is more likely to work if you remove some protals.'
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

        # Attach to each edge a list of fields that it completes
        for t in a.triangulation:
            t.markEdgesWithFields()

        agentOrder.improveEdgeOrder(a)

        with open(output_directory+output_file,'w') as fout:
            pickle.dump(a,fout)
    else:
        with open(input_file,'r') as fin:
            a = pickle.load(fin)
    #    agentOrder.improveEdgeOrder(a)
    #    with open(output_directory+output_file,'w') as fout:
    #        pickle.dump(a,fout)

    PP = PlanPrinterMap.PlanPrinter(a,output_directory,nagents,useGoogle=useGoogle)
    PP.keyPrep()
    PP.agentKeys()
    PP.planMap(useGoogle=useGoogle)
    PP.agentLinks()

    # These make step-by-step instructional images
    PP.animate(useGoogle=useGoogle)
    PP.split3instruct(useGoogle=useGoogle)

    print "Number of portals: {0}".format(PP.num_portals)
    print "Number of links: {0}".format(PP.num_links)
    print "Number of fields: {0}".format(PP.num_fields)
    portal_ap = (125*8 + 500 + 250)*PP.num_portals
    link_ap = 313 * PP.num_links
    field_ap = 1250 * PP.num_fields
    print "AP from portals capture: {0}".format(portal_ap)
    print "AP from link creation: {0}".format(link_ap)
    print "AP from field creation: {0}".format(field_ap)
    print "Total AP: {0}".format(portal_ap+link_ap+field_ap)

if __name__ == "__main__":
    main()
