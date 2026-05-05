# epydeck

![PyPI](https://img.shields.io/pypi/v/epydeck?color=blue)
![Build/Publish](https://github.com/epochpic/epydeck/actions/workflows/build_publish.yml/badge.svg)
![Tests](https://github.com/epochpic/epydeck/actions/workflows/tests.yml/badge.svg)
[![DOI](https://zenodo.org/badge/DOI/10.5281/15586339.svg)](https://doi.org/10.5281/zenodo.15586339)

Epydeck (short for *EPOCH Python deck*) is an [EPOCH](https://epochpic.github.io/) input file (deck) reader/writer. Part of [BEAM](#broad-epoch-analysis-modules-beam) (Broad EPOCH Analysis Modules).

## Installation

Install from PyPI with:

```bash
pip install epydeck
```

or from local checkout:

```bash
git clone https://github.com/epochpic/epydeck.git
cd epydeck
pip install .
```

We recommend switching to [uv](https://docs.astral.sh/uv/) to manage packages.

## Usage

> [!IMPORTANT]
> Plain numbers and bools are converted directly, everything else is
> represented as a string. Note that floating point numbers may have
> their exact form changed.

The interface follows the standard Python
[`json`](https://docs.python.org/3/library/json.html) module:

- `epydeck.load` to read from a `file` object
- `epydeck.loads` to read from an existing string
- `epydeck.dump` to write to a `file` object
- `epydeck.dumps` to write to a string

```python
import epydeck

# Read from a file with `epydeck.load`
with open(filename) as f:
    deck = epydeck.load(f)

print(deck.keys())
# dict_keys(['control', 'boundaries', 'constant', 'species', 'laser', 'output_global', 'output', 'dist_fn'])

# Modify the deck as a usual python dict:
deck["species"]["proton"]["charge"] = 2.0

# Write to file
with open(filename, "w") as f:
    epydeck.dump(deck, f)

print(epydeck.dumps(deck))
# ...
# begin:species
#   name = proton
#   charge = 2.0
#   mass = 1836.2
#   fraction = 0.5
#   number_density = if((r gt ri) and (r lt ro), den_cone, 0.0)
#   number_density = if((x gt xi) and (x lt xo) and (r lt ri), den_cone, number_density(proton))
#   number_density = if(x gt xo, 0.0, number_density(proton))
# end:species
# ...
```

<details>

<summary>Further details</summary>

Reads from file into a standard Python `dict`. Repeated blocks, such
as `species`, have an extra level of nesting using the block `name`.
Repeated keys, such as `number_density`, are represented as a single
key with a list of values. For example, the following input deck:

```text
begin:constant
  lambda = 1.06 * micron
  omega = 2 * pi * c / lambda
  den_cone = 4.0 * critical(omega)
  th = 1 * micron / 2.0
  ri = abs(x - 5*micron) - sqrt(2.0) * th
  ro = abs(x - 5*micron) + sqrt(2.0) * th
  xi = 3*micron - th
  xo = 3*micron + th
  r = sqrt(y^2 + z^2)
end:constant

begin:species
  name = proton
  charge = 1.0
  mass = 1836.2
  fraction = 0.5
  number_density = if((r gt ri) and (r lt ro), den_cone, 0.0)
  number_density = if((x gt xi) and (x lt xo) and (r lt ri), \
                      den_cone, number_density(proton))
  number_density = if(x gt xo, 0.0, number_density(proton))
end:species

begin:species
  name = electron
  charge = -1.0
  mass = 1.0
  fraction = 0.5
  number_density = number_density(proton)
end:species
```

is represented by the following `dict`:

```python
{
  'constant': {
    'lambda': '1.06 * micron',
    'omega': '2 * pi * c / lambda',
    'den_cone': '4.0 * critical(omega)',
    'th': '1 * micron / 2.0',
    'ri': 'abs(x - 5*micron) - sqrt(2.0) * th',
    'ro': 'abs(x - 5*micron) + sqrt(2.0) * th',
    'xi': '3*micron - th',
    'xo': '3*micron + th',
    'r': 'sqrt(y^2 + z^2)',
  },
  'species': {
    'proton': {
      'name': 'proton',
      'charge': 1.0,
      'mass': 1836.2,
      'fraction': 0.5,
      'number_density': [
        'if((r gt ri) and (r lt ro), den_cone, 0.0)',
        'if((x gt xi) and (x lt xo) and (r lt ri), den_cone, number_density(proton))',
        'if(x gt xo, 0.0, number_density(proton))'
      ]
    },
    'electron': {
      'name': 'electron',
      'charge': -1.0,
      'mass': 1.0,
      'fraction': 0.5,
      'number_density': 'number_density(proton)'
    }
  }
}
```

</details>

## Maths parser

After loading a deck, string values such as `'1.06 * micron'` or `'2 * pi * c / lambda'` can be resolved to numbers using `epydeck.evaluate`:

```python
import epydeck

with open(filename) as f:
    deck = epydeck.load(f)

evaluated = epydeck.evaluate(deck)
```

`evaluate` returns a copy of the deck with every expression it can resolve replaced by its numeric value. Expressions are evaluated in deck order. Each line can reference any variable defined earlier in the same block or any earlier block. Values that still depend on undefined variables after a full pass are retried automatically until no further progress can be made.

The following EPOCH physical constants are always available:

| Name | Value |
|---|---|
| `pi` | $\pi$ |
| `kb` | Boltzmann's constant |
| `me` | Electron mass |
| `qe` | Elementary charge |
| `c` | Speed of light |
| `epsilon0` | Permittivity of free space |
| `mu0` | Permeability of free space |
| `ev`, `kev`, `mev` | Electronvolt, kilo-, mega- |
| `micron`, `milli`, `micro`, `nano`, `pico`, `femto`, `atto` | SI prefixes / length units |
| `cc` | Cubic centimetre ($10^{-6}$ m$^3$) |

They can be accessed as a dictionary by calling `from epydeck import CONSTANTS`.

Some expressions cannot be reduced to a scalar at parse time and are left as strings:

- `if(a, b, c)` - conditional on spatial position
- `interpolate(interp_var, ..., n_pairs)` - piecewise spatial interpolation
- `number_density(a)` - species number density field
- `temp(a)`, `temp_{x,y,z}(a)` - species temperature field
- `{e,b}{x,y,z}` - electric / magnetic field components
- Any expression referencing a grid coordinate (`x`, `y`, `z`) or other undefined variable

> [!WARNING]
> `evaluate` executes expression strings from the deck file using `simpleeval`, which restricts execution to arithmetic operations and the whitelisted EPOCH functions. Only call this function on deck files from sources you trust.

## Citing

If epydeck contributes to a project that leads to publication, please acknowledge this by citing epydeck. This can be done by clicking the "cite this repository" button located near the top right of this page.

## Broad EPOCH Analysis Modules (BEAM)

![BEAM logo](./BEAM.png)

**BEAM** is a collection of independent yet complementary open-source tools for analysing EPOCH simulations, designed to be modular so researchers can adopt only the components they require without being constrained by a rigid framework. In line with the **FAIR principles — Findable**, **Accessible**, **Interoperable**, and **Reusable** — each package is openly published with clear documentation and versioning (Findable), distributed via public repositories (Accessible), designed to follow common standards for data structures and interfaces (Interoperable), and includes licensing and metadata to support long-term use and adaptation (Reusable). The packages are as follows:

- [sdf-xarray](https://github.com/epochpic/sdf-xarray): Reading and processing SDF files and converting them to [xarray](https://docs.xarray.dev/en/stable/).
- [epydeck](https://github.com/epochpic/epydeck): Input deck reader and writer.
- [epyscan](https://github.com/epochpic/epyscan): Create campaigns over a given parameter space using various sampling methods.

## PlasmaFAIR

![PlasmaFAIR logo](PlasmaFAIR.svg)

Originally developed by [PlasmaFAIR](https://plasmafair.github.io), EPSRC Grant EP/V051822/1