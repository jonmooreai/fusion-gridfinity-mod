# Gridfinity Generator Mod

Based on [FusionGridfinityGenerator](https://github.com/Le0Michine/FusionGridfinityGenerator) by [Le0Michine](https://github.com/Le0Michine).

<video src="fusion-plugin.mp4" controls width="640"></video>

![Gridfinity baseplate plugin](screenshot.png)

This mod adds two main changes on top of the original plugin:

## Generate baseplate from drawer dimensions

You can size the baseplate by **drawer dimensions** instead of grid units. Enter your drawer width and length (in mm or inches); the plugin computes the number of 42 mm grid units and even padding so the baseplate fits the drawer. If the result is larger than your print bed, the baseplate is split into multiple pieces that fit the build plate, with padding only on the outer edges and no extra gap between pieces.

## Export separate STL files

When a baseplate is split into multiple print plates, use the **Export STLs** button at the bottom of the baseplate dialog to export each piece as its own numbered STL file (e.g. `gridfinity-baseplate-10x6-plate-01-of-04.stl`) for use in Bambu Studio or other slicers.

## Installation

1. **Download the add-in**  
   Clone this repo or download the ZIP and unpack it to a folder on your computer (e.g. your Desktop or Documents).

2. **Add the folder in Fusion 360**  
   - Open Fusion 360.  
   - Go to **Scripts and Add-Ins**: press `Shift + S`, or use **Design → Utilities → ADD-INS**.  
   - Open the **Add-Ins** tab and click the **+** (Add) button.  
   - Browse to the folder that contains `GridfinityGeneratorMod.py` and select it. Click **OK**.

3. **Run the add-in**  
   - **GridfinityGeneratorMod** should appear in the list. Select it and click **Run**.  
   - **Gridfinity bin** and **Gridfinity baseplate** will appear in the **Create** menu in the Solid workspace.

4. **Use the baseplate command**  
   In the Solid workspace, go to **Create → Gridfinity baseplate**. Set size by units, drawer dimensions, or print plate dimensions; click **OK** to generate, or use **Export STLs** to export split plates as numbered STL files.

**Optional:** In the Add-Ins list, check **Run on Startup** for GridfinityGeneratorMod so it loads every time you open Fusion 360.
