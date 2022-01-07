#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - maxfield.py

GNU Public License
http://www.gnu.org/licenses/
Copyright(C) 2020 by
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

Original concept by jpeterbaker
January 2020 - A complete re-write of original Ingress Maxfield.
"""

import time

from .plan import Plan
from .results import Results

__version__ = '4.0'

def read_portal_file(filename):
    """
    Read a formatted portal file and return a list of portal
    coordinates

    Inputs:
      filename :: string
        The filename for the portal list

    Returns: portals
      portals :: N-length array of dictionaries
        For each portal:
        'name' the portal name
        'lon' the longitude in degrees
        'lat' the latitude in degrees
        'keys' the number of keys in hand for this portal
        'sbul' True if portal has SBUL
    """
    #
    # Loop over lines in portal file, determine portal coordinates
    # and other properties
    #
    portals = []
    with open(filename, 'r') as fin:
        has_inbound_portal = False
        for line in fin:
            #
            # Skip commented/empty lines, remove comments and newline
            #
            line = line.strip()
            if not line:
                continue
            if line[0] == '#':
                continue
            line = line.split('#')[0]
            line = line.strip()
            #
            # Split line on delimiter
            # parts[0] is always portal name
            # remaining parts are Intel URL, number of keys, and/or
            # SBUL
            #
            parts = line.split(';')
            name = parts[0]
            lon = None
            lat = None
            keys = 0
            sbul = False
            inbound = False
            for part in parts[1:]:
                part = part.strip()
                if not part:
                    # skip empty
                    continue
                if part == 'undefined':
                    # skip undefined
                    continue
                if 'pll' in part:
                    if lon is not None:
                        raise ValueError(
                            "Portal {0} has multiple Intel URLs.".
                            format(name))
                    #
                    # Get coords from formated URL
                    #
                    coord_parts = part.split('pll=')
                    if len(coord_parts) != 2:
                        raise ValueError(
                            "Portal {0} incorrect Intel URL. Did you "
                            "select a portal before clicking the link button?".format(name))
                    lat, lon = coord_parts[1].split(',')
                    lat = float(lat)
                    lon = float(lon)
                    continue
                #
                # See if this is number of keys
                #
                try:
                    try_keys = int(part.strip())
                    if keys > 0:
                        raise ValueError(
                            "Portal {0} has multiple key entries".
                            format(name))
                    keys = try_keys
                    continue
                except ValueError:
                    # not keys
                    pass
                #
                # See if this is SBUL
                #
                try_sbul = part.strip().lower() == 'sbul'
                if try_sbul and sbul:
                    raise ValueError(
                        "Portal {0} has multiple SBUL entries".
                        format(name))
                if try_sbul:
                    sbul = try_sbul
                    continue
                #
                # See if this is inbound only portal
                #
                try_inbound = part.strip().lower() == 'inbound'
                if try_inbound and inbound:
                    raise ValueError(
                        "Portal {0} has multiple inbound entries".
                            format(name))
                if try_inbound:
                    if sbul:
                        raise ValueError(
                            "Portal {0} has both SBUL and inbound flags".
                                format(name))
                    if has_inbound_portal:
                        raise ValueError("Plan has more than one inbound portal")

                    inbound = try_inbound
                    has_inbound_portal = True
                    continue
                #
                # If we get here, something is wrong!
                #
                raise ValueError(
                    "Portal {0} is improperly formatted. Unknown property: {1}".format(name, part))
            #
            # Check that longitude and latitude were obtained
            #
            if lon is None or lat is None:
                raise ValueError(
                    "Portal {0} is missing Intel URL. Did you remove all semi-colons and pound (hashtag) symbols from the portal name?".format(name))
            #
            # Check that longitude and latitude don't match a portal
            # already
            #
            skip_line = False
            for p in portals:
                if lon == p['lon'] and lat == p['lat']:
                    print("Portal list contains a duplicate URL. Skipping this duplicate line:")
                    print(line)
                    skip_line = True
                    break
            if skip_line:
                continue
            #
            # Populate portal dict and append
            #
            portals.append({'name':name, 'lon':lon, 'lat':lat,
                            'keys': keys, 'sbul': sbul, 'inbound': inbound})
    return portals

def maxfield(filename, num_agents=1, num_field_iterations=1000,
             num_cpus=1, max_route_solutions=1000,
             max_route_runtime=60,
             outdir='.', skip_plots=False, skip_step_plots=False,
             res_colors=False, google_api_key=None,
             google_api_secret=None, output_csv=False, verbose=False):
    """
    Given a portal list file, determine the optimal linking and
    fielding strategy to maximize AP, minimize walking distance, and
    minimize the number of keys needed.

    Inputs:
      filename :: string
        The filename containing the properly-formatted portal list.
      num_agents :: integer
        The number of agents in this fielding operation
      num_field_iterations :: integer
        The number of random field plans to generate before choosing
        the best. A larger number of iterations will mean the plan is
        more likely, or closer to, optimal, but it also increases
        runtime.
      num_cpus :: integer
        The number of CPUs used to generate field plans.
        If 1, do not use multiprocessing.
        If < 1, use maximum available CPUs.
        Otherwise, use this many CPUs.
      max_route_solutions :: integer
        The maximum number of agent routing solutions to generate
        before choosing the best. Once max_route_solutions or
        max_route_runtime is reached, the best routing plan is
        selected.
      max_route_runtime :: integer
        The maximum runtime of the agent routing algorithm (seconds).
        Once max_route_solutions or max_route_runtime is reached, the
        best routing plan is selected.
      outdir :: string
        The directory where results are stored. Created if it doesn't
        exist. Default is current directory.
      skip_plots :: boolean
        If True, don't generate any figures
      skip_step_plots :: boolean
        If True, don't generate link-by-link figures
      res_colors :: boolean
        If True, use resistance color scheme, otherwise enlightened
      google_api_key :: string
        If not None, use this as an API key for google maps. If None,
        do not use google maps.
      google_api_secret :: string
        If not None, use this as a signature secret for google maps.
        If None, do not use a google API signature.
      output_csv :: boolean
        If True, also output machine readable CSV files.
      verbose :: boolean
        If True, display helpful information along the way

    Returns: Nothing
    """
    start_time = time.time()
    #
    # Read portal file
    #
    portals = read_portal_file(filename)
    if verbose:
        print("Found {0} portals in portal file: {1}".
              format(len(portals), filename))
        print()
    #
    # Initialize Plan
    #
    plan = Plan(portals, num_agents=num_agents, verbose=verbose)
    #
    # Optimize Plan
    #
    plan.optimize(num_field_iterations=num_field_iterations,
                  num_cpus=num_cpus)
    #
    # Determine agent link assignments
    #
    plan.route_agents(max_route_solutions=max_route_solutions,
                      max_route_runtime=max_route_runtime)
    #
    # Generate plan output files and plots
    #
    results = Results(plan, outdir=outdir, res_colors=res_colors,
                      google_api_key=google_api_key,
                      google_api_secret=google_api_secret,
                      output_csv=output_csv,verbose=verbose)
    results.key_prep()
    results.ownership_prep()
    results.agent_key_prep()
    results.agent_assignments()
    if not skip_plots:
        results.portal_map()
        results.link_map()
        if not skip_step_plots:
            results.step_plots()
    end_time = time.time()
    if verbose:
        print("Total maxfield runtime: {0:.1f} seconds".
              format(end_time-start_time))
