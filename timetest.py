#!/usr/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - timetest.py

GNU Public License
http://www.gnu.org/licenses/
Copyright(C) 2016 by
Jonathan Baker; babamots@gmail.com
Trey Wenger; tvwenger@gmail.com

Test Maxfield run times, extrapolate to more portals or more
agents.

27 feb 2016 - tvw creation
"""

import sys
import os
import shutil
import numpy as np
import time
import makePlan
from pebble import process, TimeoutError

def worker(nportals,nagents,trial,skipplot):
    latmin = 38.
    lonmin = -78.
    print "Portals: {0}; Agents: {1}; Trial {2}; Skip Plots: {3}".format(nportals,nagents,trial,skipplot)
    # Generate random portal file
    portal_file = 'timetest_{0}_{1}_{2}_{3}.portals'.format(nportals,nagents,trial,skipplot)
    mydir = 'timetest_{0}_{1}_{2}_{3}/'.format(nportals,nagents,trial,skipplot)
    with open(portal_file,'w') as pfile:
        for foo in range(nportals):
            name = "Portal {0}".format(foo)
            lat = latmin + np.random.rand()*1.e-2
            lon = lonmin + np.random.rand()*1.e-2
            url = "https://www.ingress.com/intel?ll={0},{1}&z=18&pll={0},{1}".format(lat,lon)
            pfile.write('{0}; {1}\n'.format(name,url))
    # run maxfield
    start_time = time.time()
    args = {}
    args['google'] = False
    args['api_key'] = None
    args['num_agents'] = nagents
    args['input_file'] = portal_file
    args['output_dir'] = mydir
    args['output_file'] = 'timetest'
    args['optimal'] = False
    args['res'] = False
    args['attempts'] = 1
    args['quiet'] = True
    args['skipplot'] = skipplot
    makePlan.main(**args)
    tdiff = time.time() - start_time
    cleanup(nportals,nagents,trial,skipplot)
    print
    print
    return (nportals,nagents,trial,skipplot,tdiff)

def cleanup(nportals,nagents,trial,skipplot):
    portal_file = 'timetest_{0}_{1}_{2}_{3}.portals'.format(nportals,nagents,trial,skipplot)
    mydir = 'timetest_{0}_{1}_{2}_{3}/'.format(nportals,nagents,trial,skipplot)
    # Delete file and directory
    os.remove(portal_file)
    shutil.rmtree(mydir)

def main(min_portals=15,max_portals=60,d_portals=5,
         min_agents=1,max_agents=5,d_agents=1,
         trials=10,
         outfile='runtimes.csv',
         timeout=600):
    """
    Run a series of maxfields to estimate the runtime for a
    given number of portals and a given number of agents
    Run each test trials times
    Saves runtimes to outfile
    """
    args = []
    # Set up array of jobs
    # loop over portal number
    for nportals in range(min_portals,max_portals+1,d_portals):
        # loop over number of agents
        for nagents in range(min_agents,max_agents+1,d_agents):
            # Loop over each trial
            for trial in range(trials):
                # Once with and once without skipping plots
                for skipplot in [True,False]:
                    args.append((nportals,nagents,trial,skipplot))
    with process.Pool(4) as p:
        jobs = [p.schedule(worker,args=arg,timeout=timeout) for arg in args]
    runtimes = []
    for arg,job in zip(args,jobs):
        try:
            runtimes.append(job.get())
        except TimeoutError:
            runtimes.append((arg[0],arg[1],arg[2],arg[3],'nan'))
            cleanup(arg[0],arg[1],arg[2],arg[3])
    np.save('runtimes.npy',runtimes)
    with open(outfile,'w') as f:
        f.write('nportals, nagents, trial, skipplot, runtime\n')
        for foo in runtimes:
            nportals, nagents, trial, skipplot, runtime = foo
            f.write('{0}, {1}, {2}, {3}, {4}\n'.format(nportals,nagents,trial,skipplot,runtime))

if __name__ == "__main__":
    main()
