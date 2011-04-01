#!/usr/bin/env python
#
# Copyright 2007 Adam Ulvi, Shannon Behrens
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Take a TGA file, and force any tiles onto the background.

This is to make up for UI interface "difficulties" in PGU's leveledit.

"""

import os
import sys

import pygame

__docformat__ = "restructuredtext"


try:
    if (not len(sys.argv) == 3 or 
        not os.path.isfile(sys.argv[1])):
        raise ValueError
except:  # Catch all exceptions, not just ValueErrors.
    print >> sys.stderr, "usage: force_background.py INPUT.tga OUTPUT.tga"
    sys.exit(2)

in_f, out_f = sys.argv[1], sys.argv[2]
in_img = pygame.image.load(in_f)
out_img = in_img.copy()
w, h = in_img.get_width(), in_img.get_height()
for y in range(h):
    for x in range(w):
        (tile, bg, code, alpha) = in_img.get_at((x, y))
        if tile:
            bg, tile = tile, 0
        out_img.set_at((x, y), (tile, bg, code, alpha))
pygame.image.save(out_img, out_f)
