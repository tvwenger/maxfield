#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - results.py

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
August 2020 - A complete re-write of original Ingress Maxfield.
"""

import os
import urllib.request
import urllib.error
from io import BytesIO
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import image
from matplotlib.patches import Polygon
import imageio
from pygifsicle import optimize

# AP gained for various actions
_AP_PER_PORTAL = 1750 # assuming capture and full resonator deployment
_AP_PER_LINK = 313
_AP_PER_FIELD = 1250

# OpenStreetMap tile server (256x256 px tiles). No API key required.
_OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
_OSM_TILE_SIZE = 256
_OSM_USER_AGENT = "Ingress-Maxfield (https://github.com/tvwenger/maxfield)"

def _latlon_to_pixel(lon, lat, zoom):
    """
    Convert longitude/latitude (degrees) to global slippy-map pixel
    coordinates at a given zoom level (256px tiles).

    Inputs:
      lon, lat :: scalars
        Longitude and latitude in degrees
      zoom :: integer
        The slippy-map zoom level

    Returns: x, y
      x, y :: scalars
        The global pixel coordinates
    """
    siny = np.sin(np.deg2rad(lat))
    siny = min(max(siny, -0.9999), 0.9999)
    x = _OSM_TILE_SIZE * (0.5 + lon / 360.)
    y = _OSM_TILE_SIZE * (0.5 - np.log((1. + siny) / (1. - siny)) / (4. * np.pi))
    scale = 2 ** zoom
    return x * scale, y * scale

def _fetch_osm_background(center_lon, center_lat, zoom, size=640):
    """
    Fetch and stitch together OpenStreetMap tiles to build a
    size x size pixel background image centered on the given
    longitude/latitude at the given zoom level.

    Inputs:
      center_lon, center_lat :: scalars
        The center longitude and latitude (degrees)
      zoom :: integer
        The slippy-map zoom level
      size :: integer
        The width/height of the returned image in pixels

    Returns: image
      image :: (size, size, N) array of scalars, or None
        The stitched background image, or None if it could not be
        fetched
    """
    px_center, py_center = _latlon_to_pixel(center_lon, center_lat, zoom)
    px_min = px_center - size / 2.
    py_min = py_center - size / 2.
    num_tiles = 2 ** zoom
    tile_x_min = int(np.floor(px_min / _OSM_TILE_SIZE))
    tile_x_max = int(np.floor((px_min + size - 1) / _OSM_TILE_SIZE))
    tile_y_min = int(np.floor(py_min / _OSM_TILE_SIZE))
    tile_y_max = int(np.floor((py_min + size - 1) / _OSM_TILE_SIZE))
    full_width = (tile_x_max - tile_x_min + 1) * _OSM_TILE_SIZE
    full_height = (tile_y_max - tile_y_min + 1) * _OSM_TILE_SIZE
    full_image = None
    for tile_y in range(tile_y_min, tile_y_max + 1):
        if tile_y < 0 or tile_y >= num_tiles:
            continue
        for tile_x in range(tile_x_min, tile_x_max + 1):
            url = _OSM_TILE_URL.format(
                z=zoom, x=tile_x % num_tiles, y=tile_y)
            req = urllib.request.Request(
                url, headers={'User-Agent': _OSM_USER_AGENT})
            try:
                tile_data = urllib.request.urlopen(req, timeout=10).read()
            except OSError as err:
                print("Unable to connect to OpenStreetMap tile server: {0}".
                      format(err))
                return None
            tile_image = image.imread(BytesIO(tile_data))
            if full_image is None:
                full_image = np.zeros(
                    (full_height, full_width, tile_image.shape[2]),
                    dtype=tile_image.dtype)
            row = (tile_y - tile_y_min) * _OSM_TILE_SIZE
            col = (tile_x - tile_x_min) * _OSM_TILE_SIZE
            full_image[row:row+_OSM_TILE_SIZE,
                       col:col+_OSM_TILE_SIZE] = tile_image
    if full_image is None:
        return None
    offset_x = int(round(px_min - tile_x_min * _OSM_TILE_SIZE))
    offset_y = int(round(py_min - tile_y_min * _OSM_TILE_SIZE))
    return full_image[offset_y:offset_y+size, offset_x:offset_x+size]

class Results:
    """
    The Results object handles the saving of plan data and plots.
    """
    def __init__(self, plan, outdir='', res_colors=False,
                 skip_map_background=False,
                 output_csv=False, verbose=False):
        """
        Initialize a new Planner object.

        Inputs:
          plan :: a plan.Plan object
            The plan for which we are generating output.
          outdir :: string
            The directory where results are stored. Created if it
            doesn't already exist.
          res_colors :: boolean
            If True, use resistance color scheme, otherwise
            enlightened
          skip_map_background :: boolean
            If True, do not fetch an OpenStreetMap background for the
            plots.
          output_csv :: boolean
            If True, also output machine-readable CSV files
          verbose :: boolean
            If True, display helpful information along the way

        Returns: results
          results :: a new Results object
        """
        self.plan = plan
        self.outdir = outdir
        self.skip_map_background = skip_map_background
        self.output_csv = output_csv
        self.verbose = verbose
        #
        # Get portal indicies sorted by portal name
        #
        #self.name_order = np.argsort(
        #    [portal['name'].lower() for portal in self.plan.portals])
        #
        # Get portal indicies sorted from west (left) to east (right)
        #
        #self.pos_order = np.argsort(self.plan.portals_mer[:, 0])
        #
        # Get links, origins, and destinations in build order
        #
        link_orders = [self.plan.graph.edges[link]['order']
                       for link in self.plan.graph.edges]
        self.ordered_links = [link for _, link in
                              sorted(zip(link_orders,
                                         list(self.plan.graph.edges)))]
        self.ordered_origins = [link[0] for link in
                                self.ordered_links]
        self.ordered_destinations = [link[1] for link in
                                     self.ordered_links]
        #
        # Make sure output directory exists
        #
        if not os.path.exists(outdir):
            os.mkdir(outdir)
        #
        # Set color scheme
        #
        if res_colors:
            self.color = 'blue'
        else:
            self.color = 'green'
        #
        # Determine where to put portal labels to avoid overlapping
        # nearest portal
        #
        self.ha = ['center']*len(self.plan.portals)
        self.agent_ha = ['center']*len(self.plan.portals)
        self.va = ['center']*len(self.plan.portals)
        self.agent_va = ['center']*len(self.plan.portals)
        for i, dists in enumerate(self.plan.portals_dists):
            # find nearest except this portal which has 0 distance
            nonzero_idx = np.nonzero(dists)[0]
            nearest = nonzero_idx[np.argmin(dists[nonzero_idx])]
            if (self.plan.portals_mer[i, 0] <
                self.plan.portals_mer[nearest, 0]):
                self.ha[i] = 'right'
                self.agent_ha[i] = 'left'
            elif (self.plan.portals_mer[i, 0] >
                  self.plan.portals_mer[nearest, 0]):
                self.ha[i] = 'left'
                self.agent_ha[i] = 'right'
            if (self.plan.portals_mer[i, 1] <
                self.plan.portals_mer[nearest, 1]):
                self.va[i] = 'top'
                self.agent_va[i] = 'bottom'
            elif (self.plan.portals_mer[i, 1] >
                  self.plan.portals_mer[nearest, 1]):
                self.va[i] = 'bottom'
                self.agent_va[i] = 'top'
        #
        # Set up OpenStreetMap background, if we're using it
        #
        self.image = None
        if not self.skip_map_background:
            self.image = _fetch_osm_background(
                self.plan.LL_center[0], self.plan.LL_center[1],
                self.plan.zoom)
            if self.image is None and self.verbose:
                print("Skipping map background.")
            self.extent = [0, 640, 0, 640]

    def key_prep(self):
        """
        Save key preparation file to: outdir/key_preparation.txt

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating key preparation file.")
        fname = os.path.join(self.outdir, 'key_preparation.txt')
        if self.output_csv:
            fname_csv = os.path.join(self.outdir, 'key_preparation.csv')
            fout_csv = open(fname_csv, 'w')
        with open(fname, 'w') as fout:
            fout.write('Key Preparation: sorted by portal number\n\n')
            fout.write('Needed = total keys required\n')
            fout.write('Have = keys in inventory\n')
            fout.write('Remaining = keys necessary to farm\n')
            fout.write('# = portal number on portal map\n')
            fout.write('Name = portal name in portal file\n\n')
            fout.write('Needed ; Have ; Remaining ;   # ; Name\n')
            if self.output_csv:
                fout_csv.write('KeysNeeded, KeysHave, KeysRemaining, PortalNum, PortalName\n')
            #for i in self.name_order:
            for i in range(len(self.plan.portals)):
                needed = self.plan.graph.in_degree(i)
                have = self.plan.portals[i]['keys']
                remaining = np.max([0, needed-have])
                #fout.write(
                #    '{0:>6d} ; {1:>4d} ; {2:>9d} ; {3:>3d} : {4}\n'.
                #    format(needed, have, remaining, self.pos_order[i],
                #           self.plan.portals[i]['name']))
                fout.write(
                    '{0:>6d} ; {1:>4d} ; {2:>9d} ; {3:>3d} : {4}\n'.
                    format(needed, have, remaining, i,
                           self.plan.portals[i]['name']))
                if self.output_csv:
                    #fout_csv.write(
                    #    '{0}, {1}, {2}, {3}, {4}\n'.
                    #    format(needed, have, remaining, self.pos_order[i],
                    #           self.plan.portals[i]['name']))
                    fout_csv.write(
                        '{0}, {1}, {2}, {3}, {4}\n'.
                        format(needed, have, remaining, i,
                               self.plan.portals[i]['name']))
        if self.verbose:
            print("File saved to: {0}".format(fname))
            if self.output_csv:
                print("CSV File saved to: {0}".format(fname_csv))
        if self.output_csv:
            fout_csv.close()

    def ownership_prep(self):
        """
        Save ownership preparation file to:
        outdir/ownership_preparation.txt

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating ownership preparation file.")
        fname = os.path.join(self.outdir, 'ownership_preparation.txt')
        with open(fname, 'w') as fout:
            fout.write('Ownership Preparation: '
                       'sorted by portal number\n\n')
            fout.write('# = portal number on portal map\n')
            fout.write('Name = portal name in portal file\n\n')
            fout.write("These portals' first links are incoming. "
                       "They should be at full resonators before "
                       "linking.\n\n")
            fout.write('  # ; Name\n')
            #for i in self.name_order:
            for i in range(len(self.plan.portals)):
                if ((i in self.ordered_destinations and
                     i in self.ordered_origins and
                     (self.ordered_destinations.index(i) <
                      self.ordered_origins.index(i))) or
                        (i in self.ordered_destinations and
                         i not in self.ordered_origins)):
                    #fout.write("{0:>3d} ; {1}\n".
                    #           format(self.pos_order[i],
                    #                  self.plan.portals[i]['name']))
                    fout.write("{0:>3d} ; {1}\n".
                               format(i,
                                      self.plan.portals[i]['name']))
            fout.write("\n")
            fout.write("These portals' first links are outgoing. "
                       "Their resonators can be applied when the "
                       "first agent arrives.\n\n")
            fout.write('  # ; Name\n')
            #for i in self.name_order:
            for i in range(len(self.plan.portals)):
                if ((i in self.ordered_destinations and
                     i in self.ordered_origins and
                     (self.ordered_origins.index(i) <
                      self.ordered_destinations.index(i))) or
                        (i in self.ordered_origins and
                         i not in self.ordered_destinations)):
                    #fout.write("{0:>3d} ; {1}\n".
                    #           format(self.pos_order[i],
                    #                  self.plan.portals[i]['name']))
                    fout.write("{0:>3d} ; {1}\n".
                               format(i,
                                      self.plan.portals[i]['name']))
        if self.verbose:
            print("File saved to: {0}".format(fname))

    def agent_key_prep(self):
        """
        Save agent key preparation file to:
        outdir/agent_key_preparation.txt

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating agent key preparation file.")
        fname = os.path.join(self.outdir, 'agent_key_preparation.txt')
        if self.output_csv:
            fname_csv = os.path.join(self.outdir, 'agent_key_preparation.csv')
            fout_csv = open(fname_csv, 'w')
        with open(fname, 'w') as fout:
            fout.write("Agent Key Preparation: sorted by portal number "
                       "\n\n")
            fout.write('Needed = keys this agent requires\n')
            fout.write('# = portal number on portal map\n')
            fout.write('Name = portal name in portal file\n\n')
            if self.output_csv:
                fout_csv.write('Agent, KeysNeeded, PortalNum, Portal Name\n')
            for agent in range(self.plan.num_agents):
                fout.write('Keys for Agent {0}\n'.format(agent+1))
                fout.write('Needed ;   # ; Name\n')
                destinations = [ass['link'] for ass in
                                self.plan.assignments
                                if ass['agent'] == agent]
                #for i in self.name_order:
                for i in range(len(self.plan.portals)):
                    count = destinations.count(i)
                    if count > 0:
                        #fout.write(
                        #    "{0:>6d} ; {1:>3d} ; {2}\n".
                        #    format(count, self.pos_order[i],
                        #           self.plan.portals[i]['name']))
                        fout.write(
                            "{0:>6d} ; {1:>3d} ; {2}\n".
                            format(count, i,
                                   self.plan.portals[i]['name']))
                        if self.output_csv:
                            #fout_csv.write(
                            #    "{0}, {1}, {2}, {3}\n".
                            #    format(agent, count, self.pos_order[i],
                            #           self.plan.portals[i]['name']))
                            fout_csv.write(
                                "{0}, {1}, {2}, {3}\n".
                                format(agent, count, i,
                                       self.plan.portals[i]['name']))
                fout.write('\n')
        if self.verbose:
            print("File saved to: {0}".format(fname))
            if self.output_csv:
                print("CSV File saved to: {0}".format(fname_csv))
        if self.output_csv:
            fout_csv.close()

    def agent_assignments(self):
        """
        Save agent assignments to:
        outdir/agent_assignments.txt
        outdir/agent_1_assignment.txt
        outdir/agent_2_assignment.txt
        etc.

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating agent link assignments.")
        #
        # store each agent's link assignments
        #
        agent_assignments = [[] for _ in range(self.plan.num_agents)]
        #
        # Generate master assignment list
        #
        fname = os.path.join(self.outdir, 'agent_assignments.txt')
        if self.output_csv:
            fname_csv = os.path.join(self.outdir, 'agent_assignments.csv')
            fout_csv = open(fname_csv, 'w')
        with open(fname, 'w') as fout:
            fout.write("Agent Linking Assignments: links should be made in this order\n\n")
            fout.write("Link = the current link number\n")
            fout.write("Agent = the person making this link\n")
            fout.write("# = portal number on portal map\n")
            fout.write("Link Origin/Destination = portal name in portal file\n\n")
            fout.write("Link ; Agent ;   # ; Link Origin\n")
            fout.write("                 # ; Link Destination\n\n")
            if self.output_csv:
                fout_csv.write('LinkNum, Agent, OriginNum, OriginName, DestinationNum, DestinationName\n')
            #
            # Group assignments by arrival time
            #
            arrivals = list(set([ass['arrive'] for ass in
                                 self.plan.assignments]))
            arrivals.sort()
            link = 1
            for arrival in arrivals:
                #
                # Get the assignments happening at this arrival time
                #
                my_ass = [ass for ass in self.plan.assignments
                          if ass['arrive'] == arrival]
                for ass in my_ass:
                    # origin = np.where(
                    #     self.pos_order == ass['location'])[0][0]
                    # dest = np.where(
                    #     self.pos_order == ass['link'])[0][0]
                    origin = ass['location']
                    dest = ass['link']
                    fout.write("{0:4} ; {1:5} ; {2:3} ; {3} \n".format(
                        link, ass['agent']+1, origin,
                        self.plan.portals[origin]['name']))
                    fout.write("             ; {0:3} : {1} \n\n".format(
                        dest, self.plan.portals[dest]['name']))
                    if self.output_csv:
                        fout_csv.write('{0}, {1}, {2}, {3}, {4}, {5}\n'.format(
                            link, ass['agent']+1, origin, self.plan.portals[origin]['name'],
                            dest, self.plan.portals[dest]['name']))
                    #
                    # Save to agent assignment
                    #
                    agent_assignments[ass['agent']].append(
                        [link, origin, self.plan.portals[origin]['name'],
                         dest, self.plan.portals[dest]['name']])
                    link += 1
        if self.verbose:
            print("File saved to {0}".format(fname))
            if self.output_csv:
                print("CSV File saved to {0}".format(fname_csv))
        if self.output_csv:
            fout_csv.close()
        #
        # Generate each agent's assignment
        #
        for i, asses in enumerate(agent_assignments):
            if self.verbose:
                print("Generating link assignment for agent {0}.".format(i+1))
            fname = os.path.join(self.outdir, 'agent_{0}_assignment.txt'.format(i+1))
            with open(fname, 'w') as fout:
                fout.write("Agent {0} Linking Assignment: links should be made in this order\n\n".format(i+1))
                fout.write("Link = the current link number\n")
                fout.write("Agent = the person making this link\n")
                fout.write("# = portal number on portal map\n")
                fout.write("Link Origin/Destination = portal name in portal file\n\n")
                fout.write("Link ; Agent ;   # ; Link Origin\n")
                fout.write("                 # ; Link Destination\n\n")
                for ass in asses:
                    fout.write("{0:4} ; {1:5} ; {2:3} ; {3} \n".format(
                        ass[0], i+1, ass[1], ass[2]))
                    fout.write("             ; {0:3} : {1} \n\n".format(
                        ass[3], ass[4]))
            if self.verbose:
                print("File saved to {0}".format(fname))
        if self.verbose:
            print()

    def make_portal_fig(self):
        """
        Generate and return a matplotlib figure and axis with the
        portals placed. This is useful since we start each plot with
        the portals.

        Inputs: Nothing

        Returns: fig, ax
          The generated matplotlib Figure and Axis
        """
        fig = plt.figure(figsize=(7.6, 8))
        ax = fig.add_subplot(111)
        ax.set_position([0, 0, 1, 0.95])
        if self.image is not None:
            implot = ax.imshow(self.image, extent=self.extent,
                               zorder=0)
        ax.plot(self.plan.portals_mer[:, 0],
                self.plan.portals_mer[:, 1],
                marker='o', color=self.color, linestyle='none',
                markeredgecolor='black', markersize=10, zorder=10)
        #for i, mer in enumerate(self.plan.portals_mer[self.pos_order]):
        for i, mer in enumerate(self.plan.portals_mer):
            # ax.text(mer[0], mer[1], i, fontweight='bold',
            #         ha=self.ha[self.pos_order[i]],
            #         va=self.va[self.pos_order[i]],
            #         fontsize=16, zorder=11)
            ax.text(mer[0], mer[1], i, fontweight='bold',
                    ha=self.ha[i],
                    va=self.va[i],
                    fontsize=16, zorder=11)
        ax.set_aspect('equal')
        if self.image is not None:
            ax.axis(self.extent)
        ax.axis('off')
        return fig, ax

    def portal_map(self):
        """
        Save portal map to:
        outdir/portal_map.png

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating portal map.")
        fig, ax = self.make_portal_fig()
        ax.set_title('Portal Map: {0}'.
                     format(len(self.plan.portals)), fontsize=18)
        fname = os.path.join(self.outdir, 'portal_map.png')
        fig.savefig(fname, dpi=300)
        plt.close(fig)
        if self.verbose:
            print("File saved to: {0}".format(fname))

    def link_map(self):
        """
        Save link map to:
        outdir/link_map.png

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating link map.")
        fig, ax = self.make_portal_fig()
        for link in self.ordered_links:
            # plot link
            ax.plot(self.plan.portals_mer[link, 0],
                    self.plan.portals_mer[link, 1],
                    linestyle='-', color=self.color)
            # add patch if this link completes a field
            for fld in self.plan.graph.edges[link]['fields']:
                coords = [self.plan.portals_mer[i] for i in fld]
                patch = Polygon(coords, facecolor=self.color,
                                alpha=0.3, edgecolor='none')
                ax.add_patch(patch)
        ax.set_title('Link Map: {0} links and {1} fields'.
                     format(self.plan.graph.num_links,
                            self.plan.graph.num_fields),
                     fontsize=18)
        fname = os.path.join(self.outdir, 'link_map.png')
        fig.savefig(fname, dpi=300)
        plt.close(fig)
        if self.verbose:
            print("File saved to: {0}".format(fname))
            print()

    def step_plots(self):
        """
        Save each step frame to:
        outdir/frames/frame_00000.png
        outdir/frames/frame_00001.png
        etc.
        And generate GIF in outdir/plan_movie.gif

        Inputs: Nothing

        Returns: Nothing
        """
        if self.verbose:
            print("Generating step-by-step plots.")
        #
        # Make frame directory if necessary
        #
        outdir = os.path.join(self.outdir, 'frames')
        if not os.path.exists(outdir):
            os.mkdir(outdir)
        #
        # Base frame is portal map with agent locations
        #
        num_links = 0
        num_fields = 0
        num_ap = len(self.plan.portals)*_AP_PER_PORTAL
        fig, ax = self.make_portal_fig()
        drawn_agents = []
        agents_last_pos = []
        frames = []
        for agent in range(self.plan.num_agents):
            #
            # Find agent's first location
            #
            for ass in self.plan.assignments:
                if ass['agent'] == agent:
                    break
            else:
                raise ValueError("Could not find agent {0} in "
                                 "assignments".format(agent))
            portal_idx = ass['location']
            agents_last_pos.append(portal_idx)
            xpos = self.plan.portals_mer[portal_idx, 0]
            ypos = self.plan.portals_mer[portal_idx, 1]
            drawn_agents.append(
                ax.text(xpos, ypos, 'A{0}'.format(agent+1),
                        bbox={'facecolor':'magenta', 'alpha':0.5,
                              'pad':1},
                        fontweight='bold',
                        ha=self.agent_ha[portal_idx],
                        va=self.agent_va[portal_idx],
                        fontsize=12, zorder=12))
        ax.set_title('Time: 00:00:00  Links:    0  Fields:    0  '
                     'AP: {0:>7d}'.format(num_ap), fontsize=18)
        fname = os.path.join(outdir, 'frame_00000.png')
        fig.savefig(fname, dpi=300)
        frames.append(fname)
        #
        # Group assignments by arrival time, and plot each arrival
        # time actions as a single frame.
        #
        arrivals = list(set([ass['arrive'] for ass in
                             self.plan.assignments]))
        arrivals.sort()
        #
        # Plot agent movements, links, and fields
        #
        frame = 1
        for arrival in arrivals:
            #
            # Get the assignments happening at this arrival time
            #
            my_ass = [ass for ass in self.plan.assignments
                      if ass['arrive'] == arrival]
            #
            # Determine if agents moved since last frame
            #
            drawn_lines = []
            for ass in my_ass:
                last_origin = agents_last_pos[ass['agent']]
                this_origin = ass['location']
                if last_origin == this_origin:
                    # did not move
                    continue
                #
                # Draw movement line
                #
                line, = ax.plot([self.plan.portals_mer[last_origin, 0],
                                 self.plan.portals_mer[this_origin, 0]],
                                [self.plan.portals_mer[last_origin, 1],
                                 self.plan.portals_mer[this_origin, 1]],
                                linestyle='--', color='magenta', lw=2)
                drawn_lines.append(line)
                #
                # Update agent position
                #
                drawn_agents[ass['agent']].remove()
                drawn_agents[ass['agent']] = \
                    ax.text(self.plan.portals_mer[this_origin, 0],
                            self.plan.portals_mer[this_origin, 1],
                            'A{0}'.format(ass['agent']+1),
                            bbox={'facecolor':'magenta', 'alpha':0.5,
                                  'pad':1},
                            fontweight='bold',
                            ha=self.agent_ha[portal_idx],
                            va=self.agent_va[portal_idx],
                            fontsize=12, zorder=12)
                agents_last_pos[ass['agent']] = this_origin
            #
            # If at least one agent moved, save frame and remove
            # movement lines
            #
            if drawn_lines:
                #
                # Update title, save
                #
                hr = arrival // 3600
                mn = (arrival-hr*3600) // 60
                sc = (arrival-hr*3600-mn*60)
                ax.set_title('Time: {0:02d}:{1:02d}:{2:02d}  '
                             'Links: {3:>4d}  Fields: {4:>4d}  '
                             'AP: {5:>7d}'.
                             format(hr, mn, sc, num_links, num_fields,
                                    num_ap), fontsize=18)
                fname = os.path.join(outdir, 'frame_{0:05d}.png'.
                                     format(frame))
                frame += 1
                fig.savefig(fname, dpi=300)
                frames.append(fname)
                #
                # Remove drawn lines
                #
                for line in drawn_lines:
                    line.remove()
            #
            # Draw links and fields, new fields are red
            #
            fields_patches = []
            fields_drawn = []
            for ass in my_ass:
                link = (ass['location'], ass['link'])
                ax.plot(self.plan.portals_mer[link, 0],
                        self.plan.portals_mer[link, 1],
                        color=self.color, lw=2)
                num_links += 1
                num_ap += _AP_PER_LINK
                for fld in self.plan.graph.edges[link]['fields']:
                    coords = [self.plan.portals_mer[i] for i in fld]
                    patch = Polygon(coords, facecolor='red',
                                    alpha=0.3, edgecolor='none')
                    fields_patches.append(patch)
                    fields_drawn.append(ax.add_patch(patch))
                    num_fields += 1
                    num_ap += _AP_PER_FIELD
            #
            # Update title, save
            #
            hr = arrival // 3600
            mn = (arrival-hr*3600) // 60
            sc = (arrival-hr*3600-mn*60)
            ax.set_title('Time: {0:02d}:{1:02d}:{2:02d}  '
                         'Links: {3:>4d}  Fields: {4:>4d}  '
                         'AP: {5:>7d}'.
                         format(hr, mn, sc, num_links, num_fields,
                                num_ap), fontsize=18)
            fname = os.path.join(outdir, 'frame_{0:05d}.png'.
                                 format(frame))
            frame += 1
            fig.savefig(fname, dpi=300)
            frames.append(fname)
            #
            # Remove red patch, update to color and re-add
            #
            for patch, drawn in zip(fields_patches, fields_drawn):
                drawn.remove()
                patch.set_facecolor(self.color)
                ax.add_patch(patch)
        plt.close(fig)
        if self.verbose:
            print("Frames saved to: {0}/".format(outdir))
        #
        # Generate GIF
        #
        fname = os.path.join(self.outdir, 'plan_movie.gif')
        with imageio.get_writer(fname, mode='I', duration=0.5) as writer:
            for frame in frames:
                image = imageio.imread(frame)
                writer.append_data(image)
        optimize(fname)
        if self.verbose:
            print("GIF saved to {0}".format(fname))
            print()
