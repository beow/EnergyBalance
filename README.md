# EnergyBalance
An energy balance model for Sweden

Modelling Sweden in terms of electric energy balance during 2020 - 2021. From
this extrapolations in terms of adding more wind or nuclear energy can be
explored. The model assumes the following

Balance:
    Consumption + Export = Production + Import
If some constraints are mot fulfilled, balance may not be achieved and we'll
get either a shortage or excess of power.

Hourly data:
The simulation is based on hourly data during 2020-2021. A dataframe is
constructed with columns for Consumtion+Export, Constant (nuclear + heat,
based), Water inflow/outflow, Import/Export, Hydrogen need plus some other
parameters. All per hour. Power/Energy in GW (for one hour => GWh).

Power dispatch:
The balance equations are made such that
1. Consumtion (+ Export), Constant power and Wind power are given (that is,
"dispatched" first)
2. Water (hydro) power is used to balance production against consumption
3. If water capacity is not large or small enough for balancing, import or
export is used
4. If import or export limits are hit we get a shortage or an excess of power.

Scenario files:
* SEpresent.py
  Model of present situation (2020-2021)
* SE300wind.py
  Adding about 140 TWh wind power to present system to achieve roughly 300 TWh total production
* SE300windH2.py
  As previous but with production/consumption of green hydrogen to cover the deficits in production.
* SE300nuc.py
  Instead of wind power, adding about 140 TWh of nuclear energy to get to the same 300 TWh production.

![screenshot](https://github.com/beow/EnergyBalance/blob/main/300TWhWind.png)
