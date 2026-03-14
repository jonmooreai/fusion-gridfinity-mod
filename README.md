# Gridfinity Generator Mod

Based on [FusionGridfinityGenerator](https://github.com/Le0Michine/FusionGridfinityGenerator) by [Le0Michine](https://github.com/Le0Michine).

This mod adds two main changes on top of the original plugin:

## Generate baseplate from drawer dimensions

You can size the baseplate by **drawer dimensions** instead of grid units. Enter your drawer width and length (in mm or inches); the plugin computes the number of 42 mm grid units and even padding so the baseplate fits the drawer. If the result is larger than your print bed, the baseplate is split into multiple pieces that fit the build plate, with padding only on the outer edges and no extra gap between pieces.

## Export separate STL files

When a baseplate is split into multiple print plates, use the **Export STLs** button at the bottom of the baseplate dialog to export each piece as its own numbered STL file (e.g. `gridfinity-baseplate-10x6-plate-01-of-04.stl`) for use in Bambu Studio or other slicers.
