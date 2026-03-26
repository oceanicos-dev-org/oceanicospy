HOBO
====

HOBO data loggers are compact, battery-powered instruments used to measure environmental parameters such as
temperature and conductivity. The ``HOBOBase`` class provides a common interface for all HOBO logger implementations,
while ``HOBOTL`` and ``HOBOCL`` handle temperature and conductivity loggers respectively.

.. note::
   ``HOBOBase`` is not designed to be called directly in the code but is intended to be subclassed by specific HOBO logger implementations.

.. automodule:: oceanicospy.observations.hobo
   :members:
   :undoc-members:
   :show-inheritance:
