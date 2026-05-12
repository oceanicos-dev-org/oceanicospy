Installation: user guide
========================

.. note::
   **oceanicospy** requires Python 3.7 or later.

.. contents:: On this page
   :local:
   :depth: 3

Installation options
--------------------

The library can be installed in several ways:

Locally into a Python environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Library can be installed into a local Python environment (conda, venv, etc.):

.. code-block:: bash

   pip install oceanicospy

Verify the installation:

.. code-block:: bash

   pip show oceanicospy

You should see output similar to::

   Name: oceanicospy
   Version: 0.1.0
   Summary: A Python library for oceanographic data analysis, numerical model preprocessing, and data retrieval
   Author-email: OCEANICOS developer team <oceanicos_med@unal.edu.co>
   License: MIT

Google Colab
~~~~~~~~~~~~

Install the library in a Colab notebook cell. You may need to restart
the runtime after installation to resolve package conflicts:

.. code-block:: bash

   !pip install oceanicospy

Importing the library
---------------------

Import the full package or individual subpackages:

.. code-block:: python

   import oceanicospy                                           # full package
   from oceanicospy.observations.pressure_sensors import RBR   # specific class
   from oceanicospy.analysis import WaveSpectralAnalyzer        # specific class

.. note::
   Avoid wildcard imports (``from oceanicospy.analysis import *``) in
   production scripts — they can shadow names from other libraries.
