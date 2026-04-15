Wind forcing
============

.. toctree::
   :maxdepth: 4

The wind forcing module integrates with ERA5 to download and preprocess wind data for XBeach simulations.
It downloads hourly U10/V10 components from the CDS API, extracts the time series at a representative
location, and writes the result as an ASCII file in the format expected by XBeach.

.. autoclass:: oceanicospy.models.xbeachpy.preprocess.WindForcing
   :members:
   :undoc-members:
   :noindex:
