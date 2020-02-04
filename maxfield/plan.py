#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - plan.py

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
import multiprocessing as mp
import numpy as np
import networkx as nx
from scipy.spatial import ConvexHull
from . import geometry
from .generator import Generator, reset
from .router import Router

# AP gained for various actions
_AP_PER_PORTAL = 1750 # assuming capture and full resonator deployment
_AP_PER_LINK = 313
_AP_PER_FIELD = 1250

class Plan:
    """
    The Plan object handles the generation of the optimal fielding
    plan.
    """
    def __init__(self, portals, num_agents=1, verbose=False):
        """
        Initialize a new Plan object.

        Inputs:
          portals :: N-length list of dictionaries
            The portals read from maxfield.read_portal_file()
            Each dict has keys:
            "name" :: string :: the portal name
            "lon" :: scalar :: the longitude in degrees
            "lat" :: scalar :: the latitude in degrees
            "keys" :: integer :: the number of keys collected
            "sbul" :: boolean :: True if portal has SBUL
          num_agents :: integer
            The number of agents in this fielding operation
          verbose :: boolean
            If True, print information along the way

        Returns: a new Planner object
        """
        self.portals = portals
        self.num_agents = num_agents
        self.verbose = verbose
        #
        # Storage for agent link assignments and total build time.
        #
        self.assignments = None
        self.build_time = np.inf
        #
        # Get portal coordinates
        #
        self.portals_ll = np.column_stack(
            (np.deg2rad([portal['lon'] for portal in self.portals]),
             np.deg2rad([portal['lat'] for portal in self.portals])))
        #
        # Compute distance along sphere between each portal and each
        # other portal. Round to nearest meter.
        #
        self.portals_dists = \
            geometry.calc_spherical_distances(self.portals_ll)
        self.portals_dists = np.round(self.portals_dists)
        self.portals_dists = np.array(self.portals_dists, dtype=int)
        #
        # Convert coordinates via gnonomic projection and web
        # mercator projection. Also get the ideal zoom level and
        # center position for web mercator projection.
        #
        self.portals_gno = geometry.gnomonic_proj(self.portals_ll)
        self.portals_mer, self.zoom, self.LL_center = \
            geometry.web_mercator_proj(self.portals_ll)
        #
        # Find perimeter portals (portals along convex hull)
        #
        hull = ConvexHull(self.portals_gno)
        self.perim_portals = hull.vertices
        #
        # Initialize graph
        #
        self.graph = nx.DiGraph()
        for i, portal in enumerate(self.portals):
            self.graph.add_node(i)
            self.graph.nodes[i]['sbul'] = portal['sbul']
            self.graph.nodes[i]['keys'] = portal['keys']

    def optimize(self, num_field_iterations=100, num_cpus=1):
        """
        Generate many fielding plans and find the one that maximizes
        AP, minimizes single-agent walking distance, 
        and minimizes the number of required keys. The best graph is 
        saved to self.graph.

        Inputs:
          num_field_iterations :: integer
            The number of random field plans to generate before
            choosing the best. A larger number of iterations will
            mean the plan is more likely, or closer to, optimal, but
            it also increases runtime.
          num_cpus :: integer
            If 1, do not use multiprocessing.
            If < 1, use maximum available CPUs.
            Otherwise, use this many CPUs.

        Returns: Nothing
        """
        #
        # Generate many field plans using a Generator
        #
        generator = Generator(self)
        if num_cpus == 1:
            #
            # No multiprocessing
            #
            if self.verbose:
                print("Starting field generation with 1 CPU.")
                start_time = time.time()
            results = [generator.generate(i) for i in
                       range(num_field_iterations)]
            if self.verbose:
                print("Field generation runtime: {0:.1f} seconds.".
                      format(time.time()-start_time))
                print()
        else:
            #
            # multiprocessing
            #
            if num_cpus < 1:
                num_cpus = mp.cpu_count()
            with mp.Pool(num_cpus) as pool:
                if self.verbose:
                    print("Starting field generation with {0} CPUs.".
                          format(num_cpus))
                    start_time = time.time()
                results = pool.map(
                    generator.generate,
                    [i for i in range(num_field_iterations)])
                if self.verbose:
                    print("Field generation runtime: {0:.1f} seconds.".
                          format(time.time()-start_time))
                    print()
        #
        # Get best plan, sorted by:
        # max AP, min single agent distance, min keys
        #
        # N.B. Ideally we'd like to minimize the total build time,
        # but determining agent routes is too time consuming.
        #
        best = sorted(results,
                      key=lambda result: (-result.ap,      # max
                                          result.length,   # min
                                          result.max_keys))# min
        self.graph = best[0]
        print("==============================")
        print("Maxfield Plan Results:")
        print("    portals         = {0}".
              format(len(self.portals_gno)))
        print("    links           = {0}".
              format(self.graph.num_links))
        print("    fields          = {0}".
              format(self.graph.num_fields))
        print("    max keys needed = {0}".
              format(self.graph.max_keys))
        print("    AP from portals = {0}".
              format(self.graph.ap_portals))
        print("    AP from links   = {0}".
              format(self.graph.ap_links))
        print("    AP from fields  = {0}".
              format(self.graph.ap_fields))
        print("    TOTAL AP        = {0}".
              format(self.graph.ap))
        print("==============================")
        print()

    def route_agents(self, max_route_solutions=100,
                     max_route_runtime=60):
        """
        Determine optimal agent link assignments and routes to
        minimize build time. The assignments and build times are
        saved as attributes to the plan.

        Inputs:
          max_route_solutions :: integer
            The maximum number of agent routing solutions to generate
            before choosing the best. Once max_route_solutions or
            max_route_runtime is reached, the best routing plan is
            selected.
          max_route_runtime :: integer
            The maximum runtime of the agent routing algorithm
            (seconds). Once max_route_solutions or max_route_runtime
            is reached, the best routing plan is selected.

        Returns: Nothing
        """
        #
        # Initialize router
        #
        router = Router(self.graph, self.portals_dists,
                        self.num_agents,
                        max_route_solutions=max_route_solutions,
                        max_route_runtime=max_route_runtime)
        #
        # Optimize
        #
        if self.verbose:
            print("Optimizing agent link assignments.")
            start = time.time()
        assignments = router.route_agents()
        if self.verbose:
            print("Route optimization runtime: {0:.1f} seconds".
                  format(time.time()-start))
            print()
            print("Total plan build time: {0:.1f} minutes".
                  format(assignments[-1]['depart']/60.))
            print()
        #
        # Route optimization may have changed the build order, so
        # we should update the link and field dependencies
        #
        for i, ass in enumerate(assignments):
            self.graph.edges[ass['location'],ass['link']]['order'] = i
        reset(self.graph)
        #
        # Save attributes
        #
        self.assignments = assignments
