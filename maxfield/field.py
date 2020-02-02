#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - field.py

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

import itertools
import numpy as np

_OUTGOING_LIMIT = 8
_OUTGOING_LIMIT_SBUL = 40 # assume fully deployed with SBULs

class DeadendError(Exception):
    """
    Exception in case of failure to converge
    """
    def __init__(self, message):
        super(DeadendError, self).__init__(message)
        self.explain = message

def can_add_outbound(graph, portal):
    """
    Check if a link can be added outbound from a portal.

    Inputs:
      graph :: networkx.DiGraph object
        The graph for this plan
      portal :: integer
        The index of the origin portal
    
    Returns: can_add
      can_add :: boolean
        True if we can add another outgoing link from portal
    """
    max_out = _OUTGOING_LIMIT
    if graph.nodes[portal]['sbul']:
        max_out = _OUTGOING_LIMIT_SBUL
    return graph.out_degree(portal) < max_out

def add_link(graph, portal1, portal2, reversible=False):
    """
    Add a link to the graph from portal1 to portal2, if possible.
    Otherwise, try things in this order:
    - Adding link from portal2 to portal1
    - Reducing number of links originating from portal1
    - Reducing number of links originating from portal2
    If all fail, return DeadendError

    Inputs:
      graph :: nextworkx graph object
        The graph for this plan
      portal1 :: integer
        The index of portal portal1
      portal2 :: integer
        The index of portal portal2
      reversible :: boolean
        If True, this link can be reversed.

    Returns: Nothing
    """
    #
    # Check that edge doesn't already exist
    #
    if (graph.has_edge(portal1, portal2) or
            graph.has_edge(portal2, portal1)):
        return
    #
    # Check that we haven't already reached the outgoing link limit
    #
    num_links = len(graph.link_order)
    if can_add_outbound(graph, portal1):
        #
        # Add the edge
        #
        graph.add_edge(portal1, portal2, order=num_links,
                       reversible=reversible,
                       fields=[], depends=[])
        graph.link_order.append((portal1, portal2))
        return
    #
    # Try reversing direction
    #
    if reversible and can_add_outbound(graph, portal2):
        graph.add_edge(portal2, portal1, order=num_links,
                       reversible=reversible,
                       fields=[], depends=[])
        graph.link_order.append((portal2, portal1))
        return
    #
    # Try reducing number of links from portal1
    #
    try:
        is_reversible, p2 = \
            zip(*[((graph.edges[portal1, link[1]]['reversible'] and
                    can_add_outbound(graph, link[1])), link[1])
                  for link in graph.edges(portal1)])
    except ValueError:
        # none are reversible
        is_reversible = []
    if np.sum(is_reversible) > 0:
        #
        # Reverse one
        #
        p2 = p2[np.where(is_reversible)[0][0]]
        graph.add_edge(p2, portal1, **graph.edges[portal1, p2])
        graph.remove_edge(portal1, p2)
        old_order_idx = graph.link_order.index((portal1, p2))
        graph.link_order[old_order_idx] = (p2, portal1)
        #
        # Add new one
        #
        graph.add_edge(portal1, portal2, order=num_links,
                       reversible=reversible,
                       fields=[], depends=[])
        graph.link_order.append((portal1, portal2))
        return
    #
    # If reversible, try reducing number of links from portal2
    #
    try:
        is_reversible, p1 = \
            zip(*[((graph.edges[portal2, link[1]]['reversible'] and
                    can_add_outbound(graph, link[1])), link[1])
                  for link in graph.edges(portal2)])
    except ValueError:
        # none are reversible
        is_reversible = []
    if reversible and np.sum(is_reversible) > 0:
        #
        # Reverse one
        #
        p1 = p1[np.where(is_reversible)[0][0]]
        graph.add_edge(portal2, p1, **graph.edges[p1, portal2])
        graph.remove_edge(p1, portal2)
        old_order_idx = graph.link_order.index((p1, portal2))
        graph.link_order[old_order_idx] = (portal2, p1)
        #
        # Add new one
        #
        graph.add_edge(portal2, portal1, order=num_links,
                       reversible=reversible,
                       fields=[], depends=[])
        graph.link_order.append((portal2, portal1))
        return
    #
    # No options
    #
    raise DeadendError("All portals have maximum outgoing links.")

class Field:
    """
    A container for fields.
    """
    def __init__(self, vertices, exterior=False):
        """
        Initialize a new Field object.

        Inputs:
          vertices :: 3-length array of integers
            The indices of the portals at the vertices of this field.
            vertices[0] is the "anchor" or "nose" portal.
          exterior :: boolean
            If True, this is an exterior field or can be treated as
            one.

        Returns: Nothing
        """
        self.vertices = list(vertices)
        self.exterior = exterior
        # storage for the fields contained within this one
        self.children = []
        # storage for the portals contained within this one
        self.contents = []
        # storage for the interior portal used to split this field
        # into children
        self.splitter = None

    def get_contents(self, portals_gno):
        """
        Find portals within this field, and update self.contents

        Inputs:
          portals_gno :: (N,2) array of scalars
            The gnomonic projection of N portals

        Returns: Nothing
        """
        #
        # Get coordinates of vertices and area of field
        #
        v_gno = portals_gno[self.vertices]
        area = 0.5*(-v_gno[1, 1]*v_gno[2, 0] +
                    v_gno[0, 1]*(-v_gno[1, 0] + v_gno[2, 0]) +
                    v_gno[0, 0]*(v_gno[1, 1] - v_gno[2, 1]) +
                    v_gno[1, 0]*v_gno[2, 1])
        #
        # Determine sign of area and other useful quantities for
        # barycentric coordinates
        #
        sign = 1
        if area < 0:
            sign = -1
        s_parts = [v_gno[0, 1]*v_gno[2, 0] - v_gno[0, 0]*v_gno[2, 1],
                   v_gno[2, 1] - v_gno[0, 1],
                   v_gno[0, 0] - v_gno[2, 0]]
        t_parts = [v_gno[0, 0]*v_gno[1, 1] - v_gno[0, 1]*v_gno[1, 0],
                   v_gno[0, 1] - v_gno[1, 1],
                   v_gno[1, 0] - v_gno[0, 0]]
        #
        # Loop over all portals in graph
        #
        for i, portal_gno in enumerate(portals_gno):
            if i in self.vertices:
                # skip if this portal is one of the vertices
                continue
            #
            # use barycentric coordinates to determine if this portal
            # is within the field.
            #
            sbary = sign*(s_parts[0] + s_parts[1]*portal_gno[0] +
                          s_parts[2]*portal_gno[1])
            tbary = sign*(t_parts[0] + t_parts[1]*portal_gno[0] +
                          t_parts[2]*portal_gno[1])
            if ((sbary > 0) and (tbary > 0) and
                    (sbary + tbary < 2.*area*sign)):
                self.contents.append(i)

    def split(self):
        """
        Split this field on random interior portal, and update
        self.splitter and self.children.

        Inputs: Nothing

        Returns: Nothing
        """
        #
        # Skip if there are no interior portals
        #
        if not self.contents:
            return
        self.splitter = np.random.choice(self.contents)
        #
        # Generate children
        #
        # First is the field opposite to our anchor portal, so we can
        # treat it as an exterior field (it is the "tail").
        fld0 = Field([self.splitter, self.vertices[1], self.vertices[2]],
                     exterior=True)
        fld1 = Field([self.vertices[0], self.vertices[1], self.splitter],
                     exterior=False)
        fld2 = Field([self.vertices[0], self.vertices[2], self.splitter],
                     exterior=False)
        self.children = [fld0, fld1, fld2]

    def build_links(self, graph, portals_gno):
        """
        Build all links within this field, except for the final
        links ("jet" links).

        Inputs:
          graph :: nextworkx graph object
            The graph for this plan
          portals_gno :: (N,2) array of scalars
            The gnomonic projection of N portals

        Returns: Nothing

        Raises:
          DeadendError :: Unable to build fields
        """
        #
        # Check that this field hasn't already been completed by
        # neighbors
        #
        if ((graph.has_edge(self.vertices[0], self.vertices[1]) or
             graph.has_edge(self.vertices[1], self.vertices[0])) and
                (graph.has_edge(self.vertices[0], self.vertices[2]) or
                 graph.has_edge(self.vertices[2], self.vertices[0]))):
            raise DeadendError("Final vertex completed by neighbor(s)")
        #
        # Find portals within this field, and split into children
        #
        if not self.contents:
            self.get_contents(portals_gno)
        self.split()
        #
        # If no children, add reversible edge
        #
        if not self.children:
            add_link(graph, self.vertices[2], self.vertices[1],
                     reversible=True)
        #
        # Otherwise, recursively build children
        #
        else:
            # child 0 is opposite to our anchor portal, so we can
            # build that graph entirely
            self.children[0].build_links(graph, portals_gno)
            self.children[0].build_final_links(graph, portals_gno)
            # other children
            self.children[1].build_links(graph, portals_gno)
            self.children[2].build_links(graph, portals_gno)

    def build_final_links(self, graph, portals_gno):
        """
        Build final links for this field ("jet" links).

        Inputs:
          graph :: nextworkx graph object
            The graph for this plan
          portals_gno :: (N,2) array of scalars
            The gnomonic projection of N portals

        Returns: Nothing

        Raises:
          DeadendError :: Unable to build fields
        """
        #
        # Add jet links for this field, which can be reversible if
        # it is exterior.
        #
        if self.exterior:
            add_link(graph, self.vertices[1], self.vertices[0],
                     reversible=True)
            add_link(graph, self.vertices[2], self.vertices[0],
                     reversible=True)
        else:
            add_link(graph, self.vertices[0], self.vertices[1],
                     reversible=False)
            add_link(graph, self.vertices[0], self.vertices[2],
                     reversible=False)
        #
        # Build jet links for children
        #
        if self.children:
            self.children[1].build_final_links(graph, portals_gno)
            self.children[2].build_final_links(graph, portals_gno)

    def assign_fields_to_links(self, graph):
        """
        For each link in this field and its children, assign the list
        of fields that the link completes. Also assign dependencies
        to the links.

        Inputs: None

        Returns: Nothing
        """
        #
        # Get all three links for this field
        #
        links = [link for link in itertools.permutations(self.vertices, 2)
                 if graph.has_edge(link[0], link[1])]
        if len(links) != 3:
            raise ValueError("Field does not have three edges!")
        link_orders = [graph.edges[link]['order'] for link in links]
        #
        # Determine which link is last and completes this field
        #
        lastlink = links[np.argmax(link_orders)]
        graph.edges[lastlink]['fields'].append(self.vertices)
        #
        # If not exterior, the last link depends on the other two.
        # Childless, exterior fields can be built in any order.
        #
        if not self.exterior:
            links.remove(lastlink)
            graph.edges[lastlink]['depends'].extend(links)
        #
        # Otherwise, if the field has children, only the link
        # opposite to the anchor portal is a dependency
        #
        elif self.children:
            #
            # Determine which link is opposite. It is the one not
            # containing the anchor portal
            #
            opplink = [link for link in links if self.vertices[0] not in link][0]
            graph.edges[lastlink]['depends'].append(opplink)
        #
        # Assign fields to childrens' links
        #
        for child in self.children:
            child.assign_fields_to_links(graph)
        #
        # All links starting from within this field have to be
        # completed first
        #
        graph.edges[lastlink]['depends'].extend(self.contents)
