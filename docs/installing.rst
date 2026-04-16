Installation
============

.. note::
   **oceanicospy** is currently in beta. The test PyPI version is the recommended
   installation for users. Follow this guide for either user or developer setups.

.. contents:: On this page
   :local:
   :depth: 2


For users
---------

Google Colab (recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~

The easiest way to get started is through `Google Colab <https://colab.research.google.com>`_,
which provides a ready-to-use Python environment with most scientific libraries pre-installed.

Install the latest beta release from Test PyPI:

.. code-block:: bash

   !pip install --upgrade --index-url https://test.pypi.org/simple/ oceanicospy==0.0.1

This will also install the required dependencies. Verify the installation:

.. code-block:: bash

   !pip show oceanicospy

You should see output similar to::

   Name: oceanicospy
   Version: 0.0.1
   Summary: A handle package for most of the programming tools in the research group OCEANICOS
   Author-email: OCEANICOS developer team <oceanicos_med@unal.edu.co>
   License: MIT

Local environment
~~~~~~~~~~~~~~~~~

In a local Python environment (conda, venv, etc.) the same pip command applies —
just drop the leading ``!``:

.. code-block:: bash

   pip install --upgrade --index-url https://test.pypi.org/simple/ oceanicospy==0.0.1


Importing the library
---------------------

You can import the whole package or specific subpackages depending on what you need.

Global import with alias (recommended for interactive work):

.. code-block:: python

   import oceanicospy as ocpy

Subpackage-level import:

.. code-block:: python

   from oceanicospy.observations.pressure_sensors import RBR
   from oceanicospy.analysis import WaveSpectralAnalyzer

Wildcard import (loads everything in a subpackage):

.. code-block:: python

   from oceanicospy.analysis import *

.. note::
   Wildcard imports are convenient for exploration but can shadow names from other
   libraries. Prefer explicit imports in production scripts.


Package structure
-----------------

Running ``help(oceanicospy)`` shows the top-level subpackages:

.. code-block:: text

   PACKAGE CONTENTS
       analysis    (package)
       gis         (package)
       models      (package)
       observations (package)
       plots       (package)
       retrievals  (package)
       utils       (package)

Each subpackage is described briefly below:

- **analysis** — temporal and spectral techniques for oceanographic data (e.g. ``WaveSpectralAnalyzer``).
- **gis** — geospatial utilities for working with coastal data (e.g. shapefiles, raster data).
- **models** — preprocessing automation for numerical models such as SWAN, WW3, and XBeach.
- **observations** — readers for oceanographic instruments (RBR, AQUAlogger, AWAC, CTD, weather stations, etc.).
- **plots** — visualization utilities.
- **retrievals** — automated data retrieval from reanalysis products (ERA5) and real-time sources (UHSLC).
- **utils** — shared helper functions used across subpackages.

For developers
--------------

If you plan to contribute to **oceanicospy**, follow the steps below.
The workflow is based on the standard GitHub fork-and-pull-request model.

1. Create a GitHub account
~~~~~~~~~~~~~~~~~~~~~~~~~~

Sign up at https://github.com/signup. You can create an educational account linked to your university
email.

1. Fork the repository
~~~~~~~~~~~~~~~~~~~~~~

Go to https://github.com/oceanicos/oceanicospy and click **Fork** (top-right corner).
This creates your own copy under your GitHub account:

.. code-block:: text

   https://github.com/YOUR-USERNAME/oceanicospy


.. hint::

   Forking creates an independent copy of a repository, allowing you to
   freely experiment with changes without affecting the original project.

   For example, if the original repository is:

   .. code-block:: text

      https://github.com/original_owner/project

   Then your fork will be:

   .. code-block:: text

      https://github.com/YOUR-USERNAME/project

1. Set up SSH authentication
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

SSH is the recommended protocol for pushing and pulling commits. Generate a key
and link it to your GitHub account if you have not done so:

https://docs.github.com/en/authentication/connecting-to-github-with-ssh/adding-a-new-ssh-key-to-your-github-account

4. Clone your fork
~~~~~~~~~~~~~~~~~~

Navigate to the local folder where you want to work and run:

.. code-block:: bash

   git clone git@github.com:YOUR-USERNAME/oceanicospy.git
   cd oceanicospy

Check that your local clone points to your fork:

.. code-block:: bash

   git remote -v

You should see your fork listed as ``origin``. Optionally, add the upstream remote
so you can pull in changes from the original repo:

.. code-block:: bash

   git remote add upstream git@github.com:oceanicos/oceanicospy.git

5. Install in editable mode
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install the package in *editable* mode so that your local changes are reflected
immediately without reinstalling:

.. code-block:: bash

   pip install -e .

To also install the dependencies needed to build the documentation, use the
``docs`` optional dependency group defined in ``pyproject.toml``:

.. code-block:: bash

   pip install -e ".[docs]"

This installs:

- ``sphinx`` — documentation generator.
- ``sphinx_rtd_theme`` — Read the Docs HTML theme.
- ``sphinx-book-theme`` — alternative book-style theme.
- ``nbsphinx`` — embeds Jupyter notebooks in Sphinx docs.
- ``myst-nb`` — MyST Markdown and notebook support for Sphinx.

6. Create a feature branch
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Never commit directly to ``main`` or ``integration``. Create a descriptive branch instead:

.. code-block:: bash

   git branch YOUR-USERNAME/my-feature
   git checkout YOUR-USERNAME/my-feature

Branch names should start with your username while the team is getting familiar
with the workflow (e.g. ``jdoe/add-feature1``).

7. Make changes and commit
~~~~~~~~~~~~~~~~~~~~~~~~~~

Stage and commit your changes with a short, descriptive message:

.. code-block:: bash

   git add path/to/changed_file.py
   git commit -m "add some particular feature to certain module"

Push your branch to your fork:

.. code-block:: bash

   git push origin YOUR-USERNAME/my-feature

8. Open a pull request
~~~~~~~~~~~~~~~~~~~~~~~

On GitHub, navigate to your fork and click **Contribute → Open a pull request**.
GitHub will show a diff between your branch and ``oceanicos:main``.

Provide a clear title and description explaining *what* changed and *why*.
A maintainer will review and merge your contribution.
