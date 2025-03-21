# Introduction

`kmake` is a simple utility that automates handling of [KiCad](https://www.kicad.org/) projects.
`kmake` provides a unified way to generate KiCad production files and manage project structure.
The script can be used locally and in conjunction with CI infrastructure.
`Kmake` is developed with KiCad 8+ and CI environment in mind.
It uses the KiCad CLI where possible and [kiutils](https://github.com/mvnmgrx/kiutils) for functions that require raw file manipulation.

* [Installation](installation.md) describes the installation process.
* [Quick start](quick-start.md) presents a basic usage example.
* [Usage](usage.md) lists all commands available and presents commands syntax.
* [Development](development.md) describes requirements for development and the process of adding new commands.
