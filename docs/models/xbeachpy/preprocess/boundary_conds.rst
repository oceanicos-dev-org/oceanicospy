Boundary conditions
===================

.. toctree::
   :maxdepth: 4

The boundary conditions module generates XBeach-compatible spectral wave boundary conditions
from SWAN output files. It converts ``.out`` spectral data into individual ``.sp2`` files,
writes the corresponding ``filelist_<n>.txt`` and ``loclist.txt`` files, and fills the
boundary block of ``params.txt``.

.. autoclass:: oceanicospy.models.xbeachpy.preprocess.BoundaryConditions
   :members:
   :undoc-members:
   :noindex:
