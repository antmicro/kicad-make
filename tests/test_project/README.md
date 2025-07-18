# KiCad Test Design
This is a design used as an input for unit testing kmake commands.
It was designed in KiCad version `9.0.0` and contains components only from the [official KiCad library](https://gitlab.com/kicad/libraries).
## List of the project features:
### Schematic:
* Bus defined with array
* Bus alias 
* DNP/NotInBom/NotInSimulation components
* Hierarchical labels
* Local labels
* Global labels
* Power label with changed name
* Label negation
* Hierarchical sheets
* Differential signals
* Single-ended signals
* No connect signals
* Graphic lines
* Text
* SVG graphics
* KiCad graphics
* Multi unit symbols
* Components with alternate pin functions selected
* PNG image
* Text with non-default font
* Net class directive
* Arcs (greater than 180 deg)
* Exclude from board symbol
* ERC exclusion with comment
* Component class (via symbol field & rule area)
* Rule areas
* Table
* Net with multiple netclasses
* Manual ERC Warning/Error
* Bezier curves (sch & sym)
* Sheet level DNP, NotInBom, property
* Img with changed image origin
* Embedded font

### PCB:
* 8 signal layers asymmetric stackup
* Custom net classes
* Custom rules
* Stackup table
* Multiple layer zones
* Single layer zones
* Keepout area
* Inter-pair interactive length tuning patterns 
* Intra-pair interactive length tuning patterns
* Single-ended interactive length tuning pattern
* THT components
* SMT components
* THT/SMT components
* Footprints with 3D model
* Footprints without 3D model
* Locked/Unlocked footprints
* Locked/Unlocked tracks
* Locked/Unlocked zones
* Locked/Unlocked vias
* Locked/Unlocked text
* Locked/Unlocked knockouts
* Locked/Unlocked kibuzzard
* Hidden properties
* Visible properties
* Polygon with net assigned
* Text box
* PNG image
* Blind, buried and micro vias
* Vias with removed annular rings
* Text variables
* Planes located on only top and bottom
* Uncommon rotation angle of component
* Custom DRC rules
* Concave PCB outline with arcs and holes inside PCB
* Dimensions objects
* Custom pad shaped defined as polygons
* "Not in schematics" footprints
* Overlapping footprints with pads on top of each other
* Footprint overrides
* Text with non-default font
* Line styles
* DRC exclusion with comment
* Table (pcb & fp)
* Manual DRC Warning/Error
* Bezier curves  (pcb & fp)
* Multi channel design
* Track soldermask expansion
* Zone with cutout
* Img with changed image origin
* User layer marked as bottom/top
* Embedded font
* Footprint embdeded data
* Layer pair definition
* Via tenting settings
* Changed PTH/Via padstacks
