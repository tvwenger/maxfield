#! /usr/bin/env python
"""
Usage:
  makePlan.py [-b] [-n <agent_count>] [-s <extra_samples>] <input_file> [<output_directory>] [<output_file>]

Description:
  This is for Ingress. If you don't know what that is, you're lost.

  input_file:
      One of two types of files:

      - semi-colon delimited file formatted as portal name; link; (optional) keys

          portal name should not contain commas
          link is the portal link from the Intel map
          keys is the number of keys you have for the portal

      - .pkl an output from a previous run of this program

          this can be used to make the same plan with a different number of agents

  output_directory:
      directory in which to put all output (default is the working directory)

  output_file:
      name for a .pkl file containing information on the plan

      if you use this for the input file, the same plan will be produced with the
      number of agents you specify (default: "lastPlan.pkl")

Options:
  -b         Make maps blue instead of green
  -n agents  Number of agents [default: 1]
  -s extra_samples Number of iterations to run optimization [default: 50]  [max: 100]

Original version by jpeterbaker
22 July 2014 - tvw updates csv file format
15 August 2014 - tvw updates with google API, other things
                 switchted to ; delimited file
"""

import sys
from docopt import docopt

import networkx as nx
from lib import maxfield,PlanPrinterMap,geometry,agentOrder
import pickle

import matplotlib.pyplot as plt

def main():
    args = docopt(__doc__)

    # We will take many samples in an attempt to reduce number of keys to farm
    # This is the number of samples to take since the last improvement
    EXTRA_SAMPLES = 50

    np = geometry.np

    #GREEN = 'g'
    #BLUE  = 'b'
    GREEN = '#3BF256' # Actual faction text colors in the app
    BLUE  = '#2ABBFF'
    #GREEN = (0.0 , 1.0 , 0.0 , 0.3)
    #BLUE  = (0.0 , 0.0 , 1.0 , 0.3)
    COLOR = GREEN

    if args['-b']:
        COLOR = BLUE

    output_directory = ''
    if args['<output_directory>'] != None:
        output_directory = args['<output_directory>']
        if output_directory[-1] != '/':
            output_directory += '/'

    output_file = 'lastPlan.pkl'
    if args['<output_file>'] != None:
        output_file = args['<output_file>']
        if not output_file[-3:] == 'pkl':
            print 'WARNING: output file should end in "pkl" or you cannot use it as input later'

    nagents = int(args['-n'])
    if nagents < 0:
        print 'Number of agents should be positive'
        exit()

    EXTRA_SAMPLES = int(args['-s'])
    if EXTRA_SAMPLES < 0:
        print 'Number of extra samples should be positive'
        exit()
    elif EXTRA_SAMPLES > 100:
        print 'Extra samples may not be more than 100'
        exit()

    input_file = args['<input_file>']

    if input_file[-3:] != 'pkl':
        a = nx.DiGraph()

        locs = []

        i = 0
        # each line should be name,intel_link,keys
        with open(input_file,'r') as fin:
            for line in fin:
                parts = line.split(';')

                if len(parts) < 2:
                    break

                a.add_node(i)
                a.node[i]['name'] = parts[0].strip()

                coords = (parts[1].split('pll='))[1]
                coord_parts = coords.split(',')
                lat = int(float(coord_parts[0]) * 1.e6)
                lon = int(float(coord_parts[1]) * 1.e6)
                locs.append( np.array([lat,lon],dtype=int) )

                if len(parts) < 3:
                    a.node[i]['keys'] = 0
                else:
                    a.node[i]['keys'] = int(parts[3])

                i += 1

        if i > 65:
            print 'Limit of 65 portals may be optimized at once'
            exit()
        
        n = a.order() # number of nodes

        locs = np.array(locs,dtype=float)

        # This part assumes we're working with E6 latitude-longitude data
        locs = geometry.e6LLtoRads(locs)
        xyz  = geometry.radstoxyz(locs)
        xy   = geometry.gnomonicProj(locs,xyz)

        for i in xrange(n):
            a.node[i]['geo'] = locs[i]
            a.node[i]['xyz'] = xyz [i]
            a.node[i]['xy' ] = xy  [i]

        # EXTRA_SAMPLES attempts to get graph with few missing keys
        # Try to minimuze TK + 2*MK where
        #   TK is the total number of missing keys
        #   MK is the maximum number of missing keys for any single portal
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

    PP = PlanPrinterMap.PlanPrinter(a,output_directory,nagents,COLOR)
    PP.keyPrep()
    PP.agentKeys()
    PP.planMap()
    PP.agentLinks()

    # These make step-by-step instructional images
    PP.animate()
    PP.split3instruct()

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
    sys.exit(main())
