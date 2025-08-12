Walkthrough Example
======================

This document provides a walkthrough of how to use the `oceanicospy` package to handle observations from various sensors.

First, ensure you have the package installed. You can install it using pip test with the following command:

.. code-block:: bash

   !pip install --index-url https://test.pypi.org/simple/ oceanicospy

Next, you can import the necessary classes from the `oceanicospy.observations` module. For example, if you want to work with the AQUAlogger sensor, you can do so as follows:

.. code-block:: python

   from oceanicospy.observations import AQUAlogger

If you are not in Google Colab, you might have to import other libraries as well:

.. code-block:: python

   import pandas as pd
   import numpy as np
   import matplotlib.pyplot as plt
   from datetime import datetime, timedelta

.. note::
   If you are using Google Colab, you can skip the above imports as they are already included in the environment. 
   You only need to import the modules from ``datetime``.

   .. code-block:: python

      from datetime import datetime, timedelta

A variable ``directory_path`` is used to specify the path to the directory containing the observation files while the ``sampling_dict`` is used to definte the sampling configuration.

.. code-block:: python

   directory_path = '/path/to/your/observation/files'
   sampling_dict = {'start_time': datetime(2023, 1, 1),
                    'end_time': datetime(2023, 12, 31),
                    'sampling_rate': 1
                    }

Once both variables are set, you can create an instance of the `AQUAlogger` class by passing the directory path and sampling configuration:

.. code-block:: python

   aqualogger = AQUAlogger(directory_path, sampling_dict)
