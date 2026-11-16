"""BioTwin Singapore: horticultural-waste-to-biochar planning backend.

Modules
-------
data        load every data file once, with clear errors when one is missing
pathway     per-wet-tonne carbon ledger and plant economics by size / technology
forecast    national supply projection with backtest, spatial allocation, seasonal composition
network     origin x site road distances, LP allocation, evaluation of a hub configuration
optimise    NSGA-II over site x plant-size choices, plus exhaustive enumeration for small cases
validation  compare estimates with independent records by URA region or PWC sector
"""
__version__ = "0.3.0"
