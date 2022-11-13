# EnergyBalance
An energy balance model for Sweden

Modelling Sweden in terms of electric energy/power balance. Using windpower
data from 2020-2021 that may be scaled linearly to a requested level. Other
"must run" sources (heat, nuclear) are modelled with a sinus variation over
the year. Hydrogen production with flexibility is also included. 

Balance:
    Consumption + Export = Production + Import
If some constraints are mot fulfilled, balance may not be achieved and we'll
get either a shortage or excess of power.

Hourly data:
The simulation is based on hourly data during 2020-2021. A dataframe is
constructed with columns for Consumption, Wind, Water, Constant (nuclear + 
heat), Import/Export, Hydrogen production/flex plus some other
parameters. All per hour. Power/Energy in GW (for one hour => GWh).

Power dispatch to match Consumtion is done with the following "merit order":
1. Wind and Constant (heat/nuclear) power are "must run" sources 
2. Water (hydro) power is used to balance production against consumption
3. If not balancing, extra hydrogen production or flex
4. If not balancing, Import or Export
5. If not balancing, Shortage or Excess of power.

Scenario files:
SvK_EF_wind.py, models the SvK "Elecrification Renewable" scenario with 
mainly windpower (no nuclear).
SvK_EF_nuclear.py, models the same scenario but with mainly nuclear power.

![screenshot](https://github.com/beow/EnergyBalance/blob/main/300TWhWind.png)
