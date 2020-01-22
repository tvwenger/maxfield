#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - generator.py

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

import copy
import numpy as np
from .fielder import Fielder
from .reorder import reorder_links_origin
from .reorder import reorder_links_depends
from .reorder import get_path_length

# Timeout link reordering after this many iterations
_N_REORDER_ATTEMPTS = 100

# AP gained for various actions
_AP_PER_PORTAL = 1750 # assuming capture and full resonator deployment
_AP_PER_LINK = 313
_AP_PER_FIELD = 1250

def reset(graph):
    """
    After re-ordering links in the plan, we must reset the
    link field assignments and dependencies.

    Inputs:
      graph :: networkx.DiGraph object
        The graph we are resetting

    Returns: Nothing
    """
    for link in graph.edges:
        graph.edges[link]['depends'] = []
        graph.edges[link]['fields'] = []
    for fld in graph.firstgen_fields:
        fld.assign_fields_to_links(graph)

class Generator:
    """
    The Generator object handles the field generation for a plan.
    """
    def __init__(self, plan):
        """
        Create a new Generator object.

        Inputs:
          plan :: plan.Plan object
            The plan for which we are creating fields.

        Returns: generator
          generator :: generator.Generator object
            A new Generator object.
        """
        self.plan = plan

    def generate(self, num):
        """
        Generate a fielding plan for this graph and re-order links
        to optimize single-agent walking distance. Several attributes
        are added to the returned graph.

        N.B. Ideally we would like to re-order links in this plan to
        minimize the total plan time. Unfortunately, that requires
        determining agent assignments, which is slow. Instead, we
        re-order links to minimize the total walking distance assuming
        1 agent, which should be okay.

        Inputs:
          num :: integer
            The index of this Generator object, which is typically
            called via multiprocessing.Pool. Unused.

        Returns: graph
          graph :: nextworkx graph object
            A copy of self.plan.graph, now completed.
        """
        #
        # Copy the original graph for completion
        #
        graph = copy.deepcopy(self.plan.graph)
        #
        # Initialize fielder
        #
        fielder = Fielder(graph, self.plan.portals_gno)
        #
        # Attempt to generate fields to fill the graph
        #
        if not fielder.make_fields(self.plan.perim_portals):
            #
            # No valid solution.
            #
            return (np.inf, np.nan, np.nan, np.inf)
        #
        # Assign fields and link dependencies to all links in graph
        #
        for fld in graph.firstgen_fields:
            fld.assign_fields_to_links(graph)
        #
        # Re-arrange links to minimize build time by grouping links with
        # common origins.
        #
        reorder_links_origin(graph)
        #
        # Re-ordering may have altered fields and dependencies, so
        # reset and re-determine
        #
        reset(graph)
        #
        # Re-arrange links to minimize build time by moving blocks
        # of links around. Do so until there is no further
        # improvement or we timeout.
        #
        num_tries = 0
        while (reorder_links_depends(graph, self.plan.portals_dists)
               and num_tries < _N_REORDER_ATTEMPTS):
            #
            # Re-ordering may have altered fields and dependencies, so
            # reset and re-determine
            #
            reset(graph)
            num_tries += 1
        #
        # Determine the maximum number of keys needed for any portal
        #
        destination_portals = [link[1] for link in graph.edges]
        graph.max_keys = np.max([
            destination_portals.count(i)-portal['keys']
            for i, portal in enumerate(self.plan.portals)])
        #
        # Save link and field numbers to graph
        #
        graph.num_links = len(graph.edges)
        graph.num_fields = np.sum([len(graph.edges[link]['fields'])
                                   for link in graph.edges])
        #
        # Get final walking length if this plan for one agent
        #
        graph.length = get_path_length(graph, self.plan.portals_dists)
        #
        # Save attributes to graph and return
        #
        graph.ap_portals = _AP_PER_PORTAL * len(self.plan.portals_gno)
        graph.ap_links = _AP_PER_LINK * graph.num_links
        graph.ap_fields = _AP_PER_FIELD * graph.num_fields
        graph.ap = graph.ap_portals + graph.ap_links + graph.ap_fields
        return graph
