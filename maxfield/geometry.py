#! /usr/bin/env python
# -*- coding: utf-8 -*-
"""
Ingress Maxfield - geometry.py

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

import numpy as np

_R_EARTH = 6371000. # meters

def calc_spherical_distances(LL):
    """
    Compute the spherical distance between each longitude, latitude
    point and each other point in LL. Using the "Vincenty formula for
    an ellipsoid with equal major and minor axes" (see
    https://en.wikipedia.org/wiki/Great-circle_distance)

    Inputs:
      LL :: (N,2) array of scalars
        The longitude and latitude of N points (radians)

    Returns: sphere_dist
      sphere_dist :: (N,N) array of scalars
        The spherical distance between each of the N points
    """
    cos_lon_diff = np.cos(np.abs(LL[:, 0] - LL[:, 0][:, np.newaxis]))
    sin_lon_diff = np.sin(np.abs(LL[:, 0] - LL[:, 0][:, np.newaxis]))
    cos_lat = np.cos(LL[:, 1])
    sin_lat = np.sin(LL[:, 1])
    numer = (cos_lat[:, np.newaxis]*sin_lon_diff)**2.
    numer += (cos_lat*sin_lat[:, np.newaxis] - sin_lat*cos_lat[:, np.newaxis]*cos_lon_diff)**2.
    numer = np.sqrt(numer)
    denom = sin_lat*sin_lat[:, np.newaxis] + cos_lat*cos_lat[:, np.newaxis]*cos_lon_diff
    angles = np.arctan2(numer, denom)
    sphere_dist = _R_EARTH * angles
    return sphere_dist

def gnomonic_proj(LL):
    """
    Convert positions on the surface of the Earth to (x,y) locations
    via the gnomonic projection, centered on the centroid of the
    locations.

    Inputs:
      LL :: (N,2) array of scalars
        The longitude and latitude of N points (radians)

    Returns: xy
      xy :: (N,2) array of scalars
        The gnomonic projection of N points
    """
    lon_centroid = np.min(LL[:, 0]) + (np.max(LL[:, 0])-np.min(LL[:, 0]))/2.
    lat_centroid = np.min(LL[:, 1]) + (np.max(LL[:, 1])-np.min(LL[:, 1]))/2.
    cos_lat_centroid = np.cos(lat_centroid)
    sin_lat_centroid = np.sin(lat_centroid)
    cos_lat = np.cos(LL[:, 1])
    sin_lat = np.sin(LL[:, 1])
    #
    # Angular distance between each point and the centroid
    #
    cos_c = sin_lat_centroid*sin_lat + cos_lat_centroid*cos_lat*np.cos(LL[:, 0]-lon_centroid)
    #
    # Gnomonic projection
    #
    x = _R_EARTH*cos_lat*np.sin(LL[:, 0]-lon_centroid)/cos_c
    y = _R_EARTH*(cos_lat_centroid*sin_lat - sin_lat_centroid*cos_lat*np.cos(LL[:, 0]-lon_centroid))/cos_c
    return np.column_stack((x, y))

def web_mercator_proj(LL):
    """
    Convert positions on the surface of the Earth to (x,y) locations
    via the web mercator projection. Also return other useful things
    for Google Maps.

    Inputs:
      LL :: (N,2) array of scalars
        The longitude and latitude of N points (radians)

    Returns: xy, zoom, center
      xy :: (N,2) array of scalars
        The web mercator projection of N portals
      zoom :: integer
        The zoom level for Google Maps
      center :: [center_lon, center_lat]
        The center longitude and latitude (scalar degrees)
    """
    #
    # Web-mercator projection for a 640x640 pixel image with origin
    # at lower-left corner.
    #
    x = 256./(2.*np.pi) * (LL[:,0] + np.pi)
    y = 256./(2.*np.pi) * (np.pi - np.log(np.tan(np.pi/4. + LL[:,1]/2.)))
    #
    # Set corner to (0,0) at bottom left.
    #
    xmin = np.min(x)
    ymax = np.max(y)
    x = x - xmin
    y = ymax - y
    #
    # Determine appropriate zoom level such that the map is smaller
    # than 640 pixels on both sides. That is the maximum size allowed
    # for free static maps API.
    #
    for zoom in range(20, 0, -1):
        if np.max(x*2.**zoom) < 640. and np.max(y*2.**zoom) < 640.:
            break
    x = x*2.**zoom
    y = y*2.**zoom
    #
    # Now, center points such that there is equal padding left/right
    # and top/bottom
    #
    xpad = (640. - np.max(x))/2.
    ypad = (640. - np.max(y))/2.
    x += xpad
    y += ypad
    #
    # Get center position via inverse transformation at point 320, 320
    #
    center_lon = np.pi/128. * ((320. - xpad)/2.**zoom + xmin) - np.pi
    center_lon = np.rad2deg(center_lon)
    center_lat = np.pi - np.pi/128.*(ymax - (320. - ypad)/2.**zoom)
    center_lat = 2.*np.arctan(np.exp(center_lat)) - np.pi/2.
    center_lat = np.rad2deg(center_lat)
    return np.column_stack((x, y)), zoom, [center_lon, center_lat]
