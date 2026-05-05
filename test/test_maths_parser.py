import math
import pathlib

import pytest
from scipy.constants import (
    Boltzmann,
    c,
    electron_mass,
    elementary_charge,
    epsilon_0,
    eV,
    mu_0,
    pi,
)

import epydeck
from epydeck.maths_parser import CONSTANTS, _critical, evaluate

# --- Physical constants ---


def test_constants_values():
    assert CONSTANTS["pi"] == pytest.approx(pi)
    assert CONSTANTS["kb"] == pytest.approx(Boltzmann)
    assert CONSTANTS["me"] == pytest.approx(electron_mass)
    assert CONSTANTS["qe"] == pytest.approx(elementary_charge)
    assert CONSTANTS["c"] == pytest.approx(c)
    assert CONSTANTS["epsilon0"] == pytest.approx(epsilon_0)
    assert CONSTANTS["mu0"] == pytest.approx(mu_0)
    assert CONSTANTS["ev"] == pytest.approx(eV)
    assert CONSTANTS["kev"] == pytest.approx(1e3 * eV)
    assert CONSTANTS["mev"] == pytest.approx(1e6 * eV)
    assert CONSTANTS["micron"] == pytest.approx(1e-6)
    assert CONSTANTS["femto"] == pytest.approx(1e-15)
    assert CONSTANTS["atto"] == pytest.approx(1e-18)


# --- Simple expressions using physical constants ---


def test_femto_seconds():
    deck = epydeck.loads("""
    begin:control
      t_end = 50 * femto
    end:control
    """)
    result = evaluate(deck)
    assert result["control"]["t_end"] == pytest.approx(50e-15)


def test_micron_lengths():
    deck = epydeck.loads("""
    begin:control
      x_min = -10 * micron
    end:control
    """)
    result = evaluate(deck)
    assert result["control"]["x_min"] == pytest.approx(-10e-6)


def test_pi_expression():
    deck = epydeck.loads("""
    begin:control
      length_x = 2.0 * pi
    end:control
    """)
    result = evaluate(deck)
    assert result["control"]["length_x"] == pytest.approx(2.0 * pi)


def test_power_operator():
    deck = epydeck.loads("""
    begin:control
      a = 2^10
    end:control
    """)
    result = evaluate(deck)
    assert result["control"]["a"] == pytest.approx(1024.0)


def test_literal_integers_unchanged():
    deck = epydeck.loads("""
    begin:control
      nx = 250
      ny = 250
    end:control
    """)
    result = evaluate(deck)
    assert result["control"]["nx"] == 250
    assert result["control"]["ny"] == 250


# --- Within-block forward references ---


def test_intrablock_reference():
    """Later lines in a block can reference earlier evaluated values."""
    deck = epydeck.loads("""
    begin:control
      nx = 250
      ny = 250
      nz = 250
      nparticles = nx * ny * nz * 1.0
    end:control
    """)
    result = evaluate(deck)
    assert result["control"]["nparticles"] == pytest.approx(250**3)


def test_intrablock_negation():
    """x_max = -x_min after x_min has been evaluated."""
    deck = epydeck.loads("""
    begin:control
      x_min = -10 * micron
      x_max = -x_min
    end:control
    """)
    result = evaluate(deck)
    assert result["control"]["x_min"] == pytest.approx(-10e-6)
    assert result["control"]["x_max"] == pytest.approx(10e-6)


def test_extrablock_reference():
    deck = epydeck.loads("""
    begin:constant
      I_peak_Wcm2 = 1e+23
      lambda_L = 800e-9
      a_0 = 0.85 * sqrt((1e-18 * I_peak_Wcm2) * ((1e6 * lambda_L)^2))
	end:constant
                         
    begin:subset
  	  name = hot_electrons
  	  gamma_min = a_0 * 0.1
  	  include_species:Electron
	end:subset
    """)
    result = evaluate(deck)
    assert result["subset"]["hot_electrons"]["gamma_min"] == pytest.approx(
        21.50, rel=1e-3
    )


def test_extrablock_deferred_reference():
    deck = epydeck.loads("""
    begin:constant
      laser_focus_x = -x_min
	end:constant
                         
    begin:control
  	  x_min = -45e-6
	end:control
    """)
    result = evaluate(deck)
    assert result["constant"]["laser_focus_x"] == pytest.approx(45e-6)


# --- Constant block ---


def test_constant_block_simple():
    deck = epydeck.loads("""
    begin:constant
      lambda = 1.06 * micron
    end:constant
    """)
    result = evaluate(deck)
    assert result["constant"]["lambda"] == pytest.approx(1.06e-6)


def test_constant_block_chain():
    """Constants can reference previously defined constants in the same block."""
    deck = epydeck.loads("""
    begin:constant
      lambda = 1.06 * micron
      omega = 2 * pi * c / lambda
    end:constant
    """)
    result = evaluate(deck)
    lam = 1.06e-6
    expected_omega = 2 * pi * c / lam
    assert result["constant"]["lambda"] == pytest.approx(lam)
    assert result["constant"]["omega"] == pytest.approx(expected_omega)


def test_constant_block_cross_block():
    """Constants defined in the constant block are available in other blocks."""
    deck = epydeck.loads("""
    begin:constant
      lambda = 1.06 * micron
    end:constant

    begin:laser
      lambda = lambda
    end:laser
    """)
    result = evaluate(deck)
    assert result["laser"]["lambda"] == pytest.approx(1.06e-6)


def test_critical_function():
    deck = epydeck.loads("""
    begin:constant
      lambda = 1.06 * micron
      omega = 2 * pi * c / lambda
      den_crit = critical(omega)
    end:constant
    """)
    result = evaluate(deck)
    lam = 1.06e-6
    omega = 2 * pi * c / lam
    expected = _critical(omega)
    assert result["constant"]["den_crit"] == pytest.approx(expected)


# --- Functions ---


def test_sqrt():
    deck = epydeck.loads("""
    begin:constant
      a = sqrt(2.0)
    end:constant
    """)
    result = evaluate(deck)
    assert result["constant"]["a"] == pytest.approx(math.sqrt(2.0))


def test_exp():
    deck = epydeck.loads("""
    begin:constant
      a = exp(pi)
    end:constant
    """)
    result = evaluate(deck)
    assert result["constant"]["a"] == pytest.approx(math.exp(pi))


def test_gauss_function():
    deck = epydeck.loads("""
    begin:constant
      g = gauss(0.0, 0.0, 1.0)
    end:constant
    """)
    result = evaluate(deck)
    assert result["constant"]["g"] == pytest.approx(1.0)


def test_loge():
    deck = epydeck.loads("""
    begin:constant
      a = loge(1.0)
    end:constant
    """)
    result = evaluate(deck)
    assert result["constant"]["a"] == pytest.approx(0.0)


def test_sin_cos():
    deck = epydeck.loads("""
    begin:control
      a = sin(pi)
      b = cos(0.0)
    end:control
    """)
    result = evaluate(deck)
    assert result["control"]["a"] == pytest.approx(math.sin(pi))
    assert result["control"]["b"] == pytest.approx(1.0)


# --- if() is never evaluated ---


def test_if_left_as_string():
    deck = epydeck.loads("""
    begin:species
      name = proton
      number_density = if(x gt 0.0, 1.0, 0.0)
    end:species
    """)
    result = evaluate(deck)
    assert isinstance(result["species"]["proton"]["number_density"], str)


def test_if_with_known_vars_still_skipped():
    """Even if all variables are known, if() is not evaluated."""
    deck = epydeck.loads("""
    begin:constant
      a = if(1.0, 2.0, 3.0)
    end:constant
    """)
    result = evaluate(deck)
    assert isinstance(result["constant"]["a"], str)


# --- Expressions with unknown variables left as strings ---


def test_unknown_variable_left_as_string():
    deck = epydeck.loads("""
    begin:constant
      r = sqrt(y^2 + z^2)
    end:constant
    """)
    result = evaluate(deck)
    assert isinstance(result["constant"]["r"], str)


def test_number_density_function_left_as_string():
    deck = epydeck.loads("""
    begin:species
      name = electron
      number_density = number_density(proton)
    end:species
    """)
    result = evaluate(deck)
    assert isinstance(result["species"]["electron"]["number_density"], str)


def test_string_keywords_left_as_string():
    deck = epydeck.loads("""
    begin:boundaries
      bc_x_min = simple_laser
      bc_y_min = periodic
    end:boundaries
    """)
    result = evaluate(deck)
    assert result["boundaries"]["bc_x_min"] == "simple_laser"
    assert result["boundaries"]["bc_y_min"] == "periodic"


# --- Booleans are preserved ---


def test_booleans_preserved():
    deck = epydeck.loads("""
    begin:output_global
      force_final_to_be_restartable = T
      some_flag = F
    end:output_global
    """)
    result = evaluate(deck)
    assert result["output_global"]["force_final_to_be_restartable"] is True
    assert result["output_global"]["some_flag"] is False


# --- Full deck integration ---


def test_cone_deck():
    filename = pathlib.Path(__file__).parent / "cone.deck"
    with open(filename) as f:
        deck = epydeck.load(f)
    result = evaluate(deck)

    # Physical constant expressions should be resolved
    assert result["control"]["t_end"] == pytest.approx(50e-15)
    assert result["control"]["x_min"] == pytest.approx(-10e-6)
    assert result["control"]["x_max"] == pytest.approx(10e-6)

    # constant block: lambda, omega, den_cone, th should be numbers
    lam = 1.06e-6
    omega = 2 * pi * c / lam
    assert result["constant"]["lambda"] == pytest.approx(lam)
    assert result["constant"]["omega"] == pytest.approx(omega)
    assert result["constant"]["den_cone"] == pytest.approx(4.0 * _critical(omega))
    assert result["constant"]["th"] == pytest.approx(1e-6 / 2.0)

    assert result["laser"]["lambda"] == pytest.approx(lam)

    # Spatially-varying constants should remain as strings
    assert isinstance(result["constant"]["r"], str)
    assert isinstance(result["constant"]["ri"], str)
    assert isinstance(result["constant"]["ro"], str)

    # if() expressions in species should remain as strings
    proton = result["species"]["proton"]
    for nd in proton["number_density"]:
        assert isinstance(nd, str)
