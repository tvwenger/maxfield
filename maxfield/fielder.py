#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - fielder.py

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

import numpy as np
from .field import Field, DeadendError

# Number of attempts to complete a field in the event of a deadend
_N_FIELD_ATTEMPTS = 100

class Fielder:
    """
    The Fielder object handles the field generation for a plan.
    """
    def __init__(self, graph, portals_gno):
        """
        Create a new Fielder object.

        Inputs:
          graph :: networkx.DiGraph object
            The graph we are fielding
          portals_gno :: (N,2) array of scalars
            The gnomonic projection coordinates of N portals

        Returns: fielder
          fielder :: fielder.Fielder object
            A new Fielder object.
        """
        self.graph = graph
        self.portals_gno = portals_gno

    def reset(self, num_links, num_firstgen):
        """
        In the event that we reach a DeadendError whilst fielding,
        this function will return the graph state to its previous
        state.

        Inputs:
          num_links :: integer
            The number of links in the previous graph state
          num_firstgen :: integer
            The number of first generation fields in the previous
            graph state

        Returns: Nothing
        """
        # remove links
        for link in self.graph.link_order[num_links:]:
            self.graph.remove_edge(link[0], link[1])
        # update link order
        self.graph.link_order = \
            self.graph.link_order[:num_links]
        # update firsgen_fields
        self.graph.firstgen_fields = \
            self.graph.firstgen_fields[:num_firstgen]

    def make_fields(self, perim_portals):
        """
        Recursively generate fields to fill the graph. Do so by
        starting with a random perimeter portal and its neighbors as
        the vertices of the initial field. Build fields within that
        initial field until all interior portals are used. Then, move
        on to neighboring portals and recursively call this function.

        Inputs:
          perim_portals :: M-length array of scalars
            The indices of M portals along the convex hull

        Returns: success
          success :: boolean
            True if fielding converged
        """
        #
        # Check if we've reached the end of recursion
        #
        num_perim = len(perim_portals)
        if num_perim < 3:
            return True
        #
        # Get initial number of links and fields in graph in case we
        # need to reset. These attributes may not exist if we've
        # just started
        #
        try:
            num_links = len(self.graph.link_order)
        except AttributeError:
            num_links = 0
            self.graph.link_order = []
        try:
            num_firstgen = len(self.graph.firstgen_fields)
        except AttributeError:
            num_firstgen = 0
            self.graph.firstgen_fields = []
        #
        # Loop over random permutation of perimeter portals
        #
        for i in np.random.permutation(range(len(perim_portals))):
            #
            # Build initial field from neighboring perimeter portals
            #
            vertices = np.random.permutation(
                perim_portals[[i, i-1, (i+1)%num_perim]])
            fld = Field(vertices, exterior=True)
            #
            # Try to build fields within this field
            #
            for _ in range(_N_FIELD_ATTEMPTS):
                try:
                    fld.build_links(
                        self.graph, self.portals_gno)
                    fld.build_final_links(
                        self.graph, self.portals_gno)
                    break
                except DeadendError:
                    self.reset(num_links, num_firstgen)
            else:
                # build did not succeed, move on to next permutation
                continue
            #
            # Build succeeded, so now let's move on to neighboring
            # perimeter portals
            #
            new_perim_portals = \
                perim_portals[perim_portals != perim_portals[i]]
            if not self.make_fields(new_perim_portals):
                self.reset(num_links, num_firstgen)
                # move on to next permutation
                continue
            #
            # This field and the neighbors succeeded
            #
            self.graph.firstgen_fields.append(fld)
            return True
        #
        # There was no solution
        #
        return False
