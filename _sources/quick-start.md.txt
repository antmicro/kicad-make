# Quick start

## Help

To get available commands and help how to use `kmake`, run:

```bash
kmake -h
```

To get help about specific subcommand, call:

```bash
kmake {subcommand} -h
```

## Output generation

You need to run `kmake` in the root of the KiCad project structure:

Follow this guide to generate production output for the Open Source
[Jetson Orin Baseboard](https://github.com/antmicro/jetson-orin-baseboard).

```bash
git clone https://github.com/antmicro/jetson-orin-baseboard.git
cd jetson-orin-baseboard
```

### Gerbers

To generate Gerbers, run:

```bash
kmake gerber
```

The newly created `fab` directory will contain Gerbers for the board.

You can use [KiCad builtin Gerber Viewer](https://www.kicad.org/discover/gerber-viewer/),
[Gerbv](https://gerbv.github.io/) or similar tools to preview the Gerbers.

For example, preview Gerbers with `Gerber Viewer`, run:

```bash
gerbview fab/*
```

### Schematic in PDF format

To generate a schematic in PDF format, run:

```bash
kmake sch
```

The newly created `doc` directory will contain the schematics PDF.

### Bill of materials

To generate BoM in CSV format, run:

```bash
kmake bom
```

`*-BOM_populated.csv` file will be created in `doc` directory.

### Pick and Place files

Position files will are generated using `auxilary origin` defined in KiCad.\
For tools like [OpenPnP](https://openpnp.org/), the bottom left corner of the
PCB is the optimal origin for the position files.

`Auxilary origin` can be set to any corner of the PCB using the
`kmake aux-origin` command.

To set it to the bottom-left corner, run:

```bash
kmake aux-origin -s bl
```

Generate position files:

```bash
kmake pnp
```

The generated `.pos` and `.csv` files containing the SMD component placement data
will be placed in the `fab` folder (to export also THT components add flag `-t`).

### 3D Model

To export board 3D model in `.step` format, run:

```bash
kmake step
```

`*.step` model will be created in `3d-model` directory.
