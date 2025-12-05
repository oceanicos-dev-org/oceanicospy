# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys
from pathlib import Path
import ssl
import urllib3

sys.path.insert(0, os.path.abspath('..'))

cdsapirc_path = Path.home() / ".cdsapirc"
cdsapirc_path.write_text(
    f"url: {os.environ.get('CDSAPI_URL')}\n"
    f"key: {os.environ.get('CDSAPI_KEY')}\n"
)

os.environ['SKIP_DATA_DOWNLOAD'] = '1'
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
ssl._create_default_https_context = ssl._create_unverified_context

project = 'oceanicospy'
copyright = '2025, oceanicos'
author = 'oceanicos'
release = '0.0.1'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

suppress_warnings = ["myst.header"]  # (si usas MyST)

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.napoleon',  # Optional: for Google or NumPy-style docstrings
    'sphinx.ext.viewcode',  # Optional, for source code links
]

autodoc_member_order = 'bysource'
autodoc_typehints = 'description'
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = True
autoclass_content = "both"

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'sphinx_book_theme'
#html_static_path = ['_static']
