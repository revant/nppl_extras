# -*- coding: utf-8 -*-
from setuptools import setup, find_packages
import os

version = '0.0.1'

setup(
    name='nppl_extras',
    version=version,
    description='Frappe/ERPNext Extras for NPPL',
    author='Revant Nandgaonkar',
    author_email='revant.one@gmail.com',
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=("frappe",),
)
